"""LLM backends: Gemini (google-genai) with failover to a local OpenAI-compatible server."""
import base64, io, json, logging, os, random, re, threading, time

log = logging.getLogger("thagi.llm")

MODEL = os.environ.get("GEMINI_MODEL", "gemma-4-26b-a4b-it")
LANG_NAME = {"gu": "Gujarati (ગુજરાતી)", "hi": "Hindi (हिन्दी)", "en": "English"}


class LLMUnavailable(Exception):
    """Raised when every configured backend failed."""


PROMPT = """You are a scam detector for ordinary people in India (SMS, WhatsApp, UPI, calls, emails).
Check the {what}. Reply with ONLY one JSON object, no markdown:
{{"verdict":"red|amber|green","scam_type":"short label","reasons":["2-3 short reasons"],"red_flags_found":["specific suspicious things"],"extracted":{{"urls":[],"phones":[],"upi_ids":[],"amounts":[]}},"advice":["2-3 short steps"]}}
red = almost certainly a scam; amber = suspicious/unsure; green = genuine (e.g. a bank OTP alert with no link and no ask; "do not share OTP" is genuine).
Calibration: GREEN for genuine transactional or promotional messages from telcos (Jio, Airtel, Vi, BSNL recharge/plan/validity/data/offer/expiry reminders), banks (debit/credit/UPI alerts, EMI and card due reminders), e-commerce/delivery, utility bills and tickets, when they do not ask for money to a stranger, OTP, PIN, card details or passwords and any link is on an official domain; offers, "recharge now", "offer expires" and plan expiry reminders are normal, NOT suspicious. An OTP given WITH a notice not to share it is GREEN. An e-commerce delivery OTP that says to give it to the delivery partner ONLY at the time of delivery is GREEN. RED when a person/message asks the user to share, tell, read out or send an OTP/PIN/CVV/password/card details to anyone (executive, officer, agent, caller, number) or to verify/cancel/refund/avoid a block, even if it also shows an OTP; also fake KYC/prize/refund/job/loan-threat/blackmail/authority-arrest asks, and lookalike or shortened links. Do not mark amber merely because a message has a link, an amount or the words urgent/expires.
Real banks never ask for OTP/PIN/CVV, never send collect requests to give money, never ask fees to release prizes or parcels.
verdict must be exactly red, amber or green. Write ALL text (scam_type, reasons, red_flags_found, advice) in {language}, even scam_type; only the verdict stays English. Advice may include: do not pay/click, block sender, report to 1930 or cybercrime.gov.in.
{text_part}"""


def build_prompt(text, lang, has_image):
    what = "screenshot (and message text below, if any)" if has_image else "message below"
    tp = f"\nMessage text:\n\"\"\"\n{text}\n\"\"\"" if text else ""
    return PROMPT.format(what=what, language=LANG_NAME.get(lang, "English"), text_part=tp)


def _strip_noise(s):
    s = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", s, flags=re.S | re.I)
    s = re.sub(r"<\|channel\>thought.*?<channel\|>", "", s, flags=re.S)  # gemma thought channel
    s = re.sub(r"```(?:json|JSON)?", "", s)
    return s


def _first_object(s):
    """Return the first balanced {...} substring (string-aware), else None."""
    i = s.find("{")
    while i != -1:
        depth, in_str, esc = 0, False, False
        for j in range(i, len(s)):
            c = s[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    cand = s[i:j + 1]
                    try:
                        json.loads(cand)
                        return cand
                    except ValueError:
                        break
        i = s.find("{", i + 1)
    return None


def _list(v):
    if v is None:
        return []
    if isinstance(v, (str, int, float)):
        return [str(v)]
    return [str(x) for x in v if x is not None and str(x).strip()]


def parse_json(raw):
    """Parse model output into a normalized dict. Raises ValueError if unusable."""
    if not raw or not isinstance(raw, str):
        raise ValueError("empty model output")
    obj_s = _first_object(_strip_noise(raw)) or _first_object(raw)
    if not obj_s:
        raise ValueError("no JSON object found")
    d = json.loads(obj_s)
    if not isinstance(d, dict):
        raise ValueError("JSON is not an object")
    v = str(d.get("verdict", "")).strip().lower()
    v = {"high": "red", "medium": "amber", "low": "green", "yellow": "amber", "orange": "amber", "safe": "green"}.get(v, v)
    if v not in ("red", "amber", "green"):
        raise ValueError(f"bad verdict {v!r}")
    ex = d.get("extracted") if isinstance(d.get("extracted"), dict) else {}
    return {
        "verdict": v,
        "scam_type": str(d.get("scam_type") or "").strip(),
        "reasons": _list(d.get("reasons")),
        "red_flags_found": _list(d.get("red_flags_found")),
        "extracted": {k: _list(ex.get(k)) for k in ("urls", "phones", "upi_ids", "amounts")},
        "advice": _list(d.get("advice")),
    }


# ---------------- backends ----------------
MAX_SIDE = int(os.environ.get("IMG_MAX_SIDE", "1024"))


def shrink_image(image, mime):
    """Downscale so the long side <= MAX_SIDE and re-encode as JPEG q85 (smaller/faster upload + fewer image tokens).
    Returns (bytes, mime). On any problem returns the original untouched."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(image))
        im.load()
        if max(im.size) > MAX_SIDE:
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        if im.mode != "RGB":
            bg = Image.new("RGB", im.size, (255, 255, 255))
            rgba = im.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            im = bg
        out = io.BytesIO()
        im.save(out, "JPEG", quality=85)
        data = out.getvalue()
        return data, "image/jpeg"
    except Exception:
        return image, mime


def _is_transient(e):
    s = str(e)
    return any(k in s for k in ("429", "RESOURCE_EXHAUSTED", "Timeout", "timed out", "504", "503", "DEADLINE")) or type(e).__name__ in ("ReadTimeout", "ConnectTimeout", "TimeoutException")


def _gemini(text, image, mime, lang, timeout_s=None, prompt=None, max_tokens=None, api_key=None):
    # api_key = the caller's own key (auth mode): used for this request only, fresh client, server key never read
    key = api_key or (None if api_key is not None else (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")))
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=int((timeout_s or 25) * 1000)))
    prompt = prompt or build_prompt(text, lang, bool(image))
    # gemma-4-26b-a4b-it: thinking_level=MINIMAL works (~4s vs ~20-60s); thinking_budget and LOW are rejected (400).
    cfg_kw = dict(max_output_tokens=max_tokens or int(os.environ.get("GEMINI_MAX_TOKENS", "1000")), temperature=0.1)
    levels = os.environ.get("GEMINI_THINKING", "MINIMAL")
    if levels.lower() != "default":
        cfg_kw["thinking_config"] = types.ThinkingConfig(thinking_level=levels.upper())
    cfg = types.GenerateContentConfig(**cfg_kw)

    def gen(contents):
        try:
            return client.models.generate_content(model=MODEL, contents=contents, config=cfg).text
        except Exception as e:
            if "thinking" in str(e).lower() and "not supported" in str(e).lower():  # model rejects thinking cfg -> retry plain
                plain = types.GenerateContentConfig(max_output_tokens=cfg_kw["max_output_tokens"], temperature=0.1)
                return client.models.generate_content(model=MODEL, contents=contents, config=plain).text
            raise

    if not image:
        return gen([prompt])
    img, m = shrink_image(image, mime)
    try:
        return gen([types.Part.from_bytes(data=img, mime_type=m), prompt])  # image BEFORE text
    except Exception as e:
        if _is_transient(e):  # don't burn another 25s on the Files API; fail over fast
            raise
        f = client.files.upload(file=io.BytesIO(img), config=types.UploadFileConfig(mime_type=m))
        return gen([f, prompt])


def _local(text, image, mime, lang, timeout_s=None, prompt=None, max_tokens=None):
    import httpx
    base = os.environ.get("LOCAL_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    model = os.environ.get("LOCAL_MODEL", "gemma4:e4b")
    content = []
    if image:
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(image).decode()}"}})
    content.append({"type": "text", "text": prompt or build_prompt(text, lang, bool(image))})
    r = httpx.post(f"{base}/chat/completions", timeout=float(os.environ.get("LOCAL_TIMEOUT", "120")),
                   headers={"Authorization": "Bearer " + os.environ.get("LOCAL_API_KEY", "local")},
                   json={"model": model, "messages": [{"role": "user", "content": content}], "temperature": 0.1})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


BACKENDS = {"gemini": _gemini, "local": _local}


_SEM = threading.BoundedSemaphore(int(os.environ.get("LLM_CONCURRENCY", "4")))
TOTAL_BUDGET = float(os.environ.get("LLM_BUDGET_S", "28"))


_SECRET = [(re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), "<key>"),
           (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=\-]{8,}"), "Bearer <token>"),
           (re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]*"), "<jwt>"),
           (re.compile(r"(?i)(x-gemini-key|x-goog-api-key|api[_-]?key)(\W{1,4})[A-Za-z0-9._\-]{8,}"), r"\1\2<key>")]


def scrub(s):
    """Redact API keys / bearer tokens / JWTs from any string before it is logged."""
    for rx, rep in _SECRET:
        s = rx.sub(rep, s)
    for env in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GOOGLE_API_KEY"):  # literal server keys, whatever their format
        v = os.environ.get(env, "")
        if len(v) >= 8:
            s = s.replace(v, "<key>")
    return s


class UserKeyError(Exception):
    """The caller's own Gemini key was rejected / rate limited (auth mode). Mapped to a JSON error, never a silent fallback."""
    def __init__(self, code, status, message):
        super().__init__(message)
        self.code, self.status, self.message = code, status, message


def _classify(e):
    """'key' = the API key itself is bad, 'rate' = quota/429, else None."""
    s, code = str(e), getattr(e, "code", None)
    if code == 429 or "429" in s or "RESOURCE_EXHAUSTED" in s:
        return "rate"
    if code in (401, 403) or any(k in s for k in ("API key not valid", "API_KEY_INVALID", "PERMISSION_DENIED", "UNAUTHENTICATED", "API key expired")):
        return "key"
    return None


KEY_ERR = UserKeyError("gemini_key_invalid", 400, "Your Gemini API key was rejected by Google. Check it at aistudio.google.com/apikey and try again.")
RATE_ERR = UserKeyError("gemini_rate_limited", 429, "Your Gemini API key hit its rate limit or quota. Wait a minute and try again.")


def _user_error(e):
    c = _classify(e)
    return KEY_ERR if c == "key" else RATE_ERR if c == "rate" else None


def _describe(e):
    """Exception class + short message, with anything key-like scrubbed."""
    return f"{type(e).__name__}: {scrub(str(e)).replace(chr(10), ' ')[:200]}"


def _plan(api_key):
    """Gemini attempt plan [(key|None, label)]. BYO key (auth mode): the caller's key twice, nothing else.
    Server path: primary key twice (one retry), then the OPTIONAL failover key GEMINI_API_KEY_2 once. None = primary env key."""
    if api_key is not None:
        return [(api_key, "user"), (api_key, "user")]
    primary = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    key2 = os.environ.get("GEMINI_API_KEY_2")
    if primary:
        return [(None, "primary"), (None, "primary")] + ([(key2, "key2")] if key2 else [])
    return [(key2, "key2"), (key2, "key2")] if key2 else [(None, "primary"), (None, "primary")]


def _may_continue(plan, i, prev, deadline):
    """Decide (and wait) before attempt i. prev = (label, kind) of the previous failure. Same key: retry once after ~0.8-1.4s
    jitter on a transient error (429/503/timeout) or at once on a parse error; failover key: only after a transient error.
    Never starts a retry that cannot finish inside the budget."""
    if prev is None:
        return True
    plabel, pkind = prev
    if plan[i][1] == plabel:
        if pkind == "transient":
            pause = random.uniform(0.8, 1.4)
            if deadline - time.time() - pause < 4:
                return False
            time.sleep(pause)
        return pkind in ("transient", "parse")
    return pkind == "transient"


def _gemini_with_retry(text, image, mime, lang, deadline, api_key=None):
    """Gemini call + parse. Server key: primary, one retry on the primary (jittered ~1s on 429/503/timeout), then GEMINI_API_KEY_2 once
    (optional), all inside the deadline. BYO key: only the caller's key (retry once), invalid key => KEY_ERR, never a fallback."""
    last, prev, plan = None, None, _plan(api_key)
    for attempt, (key, label) in enumerate(plan, 1):
        if deadline - time.time() < 4 or not _may_continue(plan, attempt - 1, prev, deadline):
            break
        left = deadline - time.time()
        t0 = time.time()
        try:
            with _SEM:
                t_s = min(float(os.environ.get("GEMINI_TIMEOUT_MS", "15000")) / 1000, left)
                raw = BACKENDS["gemini"](text, image, mime, lang, t_s) if key is None else \
                    BACKENDS["gemini"](text, image, mime, lang, t_s, api_key=key)
            res = parse_json(raw)
            log.info("gemini ok attempt=%d key=%s %.1fs lang=%s", attempt, label, time.time() - t0, lang)
            return res
        except Exception as e:
            last = e
            if api_key is not None and _user_error(e) is KEY_ERR:
                raise KEY_ERR
            kind = "parse" if isinstance(e, ValueError) else ("transient" if _is_transient(e) else "error")
            log.warning("gemini fail attempt=%d key=%s %.1fs lang=%s kind=%s %s", attempt, label, time.time() - t0, lang, kind, _describe(e))
            if kind == "error":
                break
            prev = (label, kind)
    if api_key is not None and last is not None and _user_error(last) is RATE_ERR:
        raise RATE_ERR
    raise last or RuntimeError("no time left for gemini")


def check(text="", image=None, mime="image/png", lang="en", api_key=None):
    """Returns (result_dict, source). Tries gemini->local (or just local). Raises LLMUnavailable if all fail.
    With api_key (auth mode): ONLY Gemini with that key - no local, no server key; a bad key / rate limit raises UserKeyError."""
    order = ["local"] if os.environ.get("LLM_BACKEND", "gemini").lower() == "local" else ["gemini", "local"]
    if api_key is not None:
        order = ["gemini"]
    errors, deadline = [], time.time() + TOTAL_BUDGET
    for name in order:
        try:
            if name == "gemini":
                return _gemini_with_retry(text, image, mime, lang, deadline, api_key), name
            return parse_json(BACKENDS[name](text, image, mime, lang)), name
        except UserKeyError:
            raise
        except Exception as e:  # 429 / network / API / parse error -> next backend
            errors.append(f"{name}: {_describe(e)}")
            log.warning("backend %s failed: %s", name, _describe(e))
    raise LLMUnavailable("; ".join(errors))


def draft_text(prompt, validate, max_tokens=2000, api_key=None):
    """Text-only generation for the complaint drafter. Gemini (<=15s, one quick retry on parse/transient error)
    -> local -> raises LLMUnavailable. `validate(raw)` must return the parsed value or raise ValueError.
    Logs exception class only (never the prompt, response or personal details). Returns (value, source)."""
    order = ["local"] if os.environ.get("LLM_BACKEND", "gemini").lower() == "local" else ["gemini", "local"]
    if api_key is not None:  # auth mode: caller's own key only, no local / server fallback
        order = ["gemini"]
    deadline, errors, last = time.time() + TOTAL_BUDGET, [], None
    for name in order:
        plan = _plan(api_key) if name == "gemini" else [(None, "local")]
        prev = None
        for attempt, (key, label) in enumerate(plan, 1):
            if deadline - time.time() < 4 or not _may_continue(plan, attempt - 1, prev, deadline):
                break
            left = deadline - time.time()
            try:
                fn = _gemini if name == "gemini" else _local
                with _SEM:
                    kw = {"api_key": key} if key is not None else {}
                    raw = fn("", None, "", "en", timeout_s=min(float(os.environ.get("GEMINI_TIMEOUT_MS", "15000")) / 1000, left),
                             prompt=prompt, max_tokens=max_tokens, **kw)
                return validate(raw), name
            except Exception as e:
                last = e
                if api_key is not None and _user_error(e) is KEY_ERR:
                    raise KEY_ERR
                kind = "parse" if isinstance(e, ValueError) else ("transient" if _is_transient(e) else "error")
                errors.append(f"{name}:{type(e).__name__}")
                log.warning("draft_text %s attempt=%d key=%s failed kind=%s %s", name, attempt, label, kind, type(e).__name__)
                if kind == "error" or name == "local":
                    break
                prev = (label, kind)
    if api_key is not None and last is not None and _user_error(last) is RATE_ERR:
        raise RATE_ERR
    raise LLMUnavailable("; ".join(errors) or "no time left")
