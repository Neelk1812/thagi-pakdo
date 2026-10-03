"""LLM backends: Gemini (google-genai) with failover to a local OpenAI-compatible server."""
import base64, io, json, os, re

MODEL = os.environ.get("GEMINI_MODEL", "gemma-4-26b-a4b-it")
LANG_NAME = {"gu": "Gujarati (ગુજરાતી)", "hi": "Hindi (हिन्दी)", "en": "English"}


class LLMUnavailable(Exception):
    """Raised when every configured backend failed."""


PROMPT = """You are a scam detector for ordinary people in India (SMS, WhatsApp, UPI, calls, emails).
Check the {what}. Reply with ONLY one JSON object, no markdown:
{{"verdict":"red|amber|green","scam_type":"short label","reasons":["2-3 short reasons"],"red_flags_found":["specific suspicious things"],"extracted":{{"urls":[],"phones":[],"upi_ids":[],"amounts":[]}},"advice":["2-3 short steps"]}}
red = almost certainly a scam; amber = suspicious/unsure; green = genuine (e.g. a bank OTP alert with no link and no ask; "do not share OTP" is genuine).
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


def _gemini(text, image, mime, lang):
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=int(os.environ.get("GEMINI_TIMEOUT_MS", "25000"))))
    prompt = build_prompt(text, lang, bool(image))
    # gemma-4-26b-a4b-it: thinking_level=MINIMAL works (~4s vs ~20-60s); thinking_budget and LOW are rejected (400).
    cfg_kw = dict(max_output_tokens=int(os.environ.get("GEMINI_MAX_TOKENS", "1000")), temperature=0.1)
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


def _local(text, image, mime, lang):
    import httpx
    base = os.environ.get("LOCAL_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    model = os.environ.get("LOCAL_MODEL", "gemma4:e4b")
    content = []
    if image:
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(image).decode()}"}})
    content.append({"type": "text", "text": build_prompt(text, lang, bool(image))})
    r = httpx.post(f"{base}/chat/completions", timeout=float(os.environ.get("LOCAL_TIMEOUT", "120")),
                   headers={"Authorization": "Bearer " + os.environ.get("LOCAL_API_KEY", "local")},
                   json={"model": model, "messages": [{"role": "user", "content": content}], "temperature": 0.1})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


BACKENDS = {"gemini": _gemini, "local": _local}


def check(text="", image=None, mime="image/png", lang="en"):
    """Returns (result_dict, source). Tries gemini->local (or just local). Raises LLMUnavailable if all fail."""
    order = ["local"] if os.environ.get("LLM_BACKEND", "gemini").lower() == "local" else ["gemini", "local"]
    errors = []
    for name in order:
        try:
            return parse_json(BACKENDS[name](text, image, mime, lang)), name
        except Exception as e:  # 429 / network / API / parse error -> next backend
            errors.append(f"{name}: {type(e).__name__}: {str(e)[:200]}")
    raise LLMUnavailable("; ".join(errors))
