"""Thagi Pakdo - scam checker backend. Run: uvicorn app:app"""
import hashlib, io, json, logging, os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from typing import Literal

ROOT = Path(__file__).parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("thagi.app")

_orig_factory = logging.getLogRecordFactory()


def _scrubbing_factory(*args, **kw):  # every log line passes through llm.scrub: no API keys / bearer tokens / JWTs, ever
    rec = _orig_factory(*args, **kw)
    try:
        rec.msg, rec.args = llm.scrub(rec.getMessage()), ()
    except Exception:
        pass
    return rec


def load_dotenv(path=ROOT / ".env"):
    """Tiny .env parser (KEY=VALUE, # comments, optional quotes / 'export '). Never overrides vars already set."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip().removeprefix("export ").strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        elif " #" in v:
            v = v.split(" #", 1)[0].strip()
        if k and k not in os.environ:
            os.environ[k] = v


load_dotenv()  # must run before llm reads env

import auth, checks, complaint as cmp, llm
logging.setLogRecordFactory(_scrubbing_factory)
WEB = ROOT / "web"
CACHE = Path(os.environ.get("CACHE_DIR") or ROOT / "sample_cache")
SAMPLES = ROOT / "samples"
MAX_IMG = 8 * 1024 * 1024
MAX_TEXT = 5000
LANGS = ("gu", "hi", "en")

app = FastAPI(title="Thagi Pakdo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])  # incl. Authorization, X-Gemini-Key


@app.exception_handler(auth.AuthError)
async def _auth_error(request, exc):
    return JSONResponse({"error": exc.code, "message": exc.message}, status_code=exc.status)


@app.exception_handler(llm.UserKeyError)
async def _user_key_error(request, exc):
    return JSONResponse({"error": exc.code, "message": exc.message}, status_code=exc.status)

# ---- localized code-only fallback text ----
R = {  # category -> {lang: reason}
    "shortener": {"en": "The link is shortened, so you can't see where it really goes.",
                  "hi": "लिंक छोटा किया हुआ है, इसलिए पता नहीं चलता कि यह असल में कहाँ ले जाएगा।",
                  "gu": "લિંક ટૂંકી કરેલી છે, તેથી તે ખરેખર ક્યાં લઈ જશે તે ખબર પડતી નથી."},
    "lookalike": {"en": "The website name imitates a real bank/company (fake lookalike address).",
                  "hi": "वेबसाइट का नाम असली बैंक/कंपनी की नकल करता है (नकली मिलता-जुलता पता)।",
                  "gu": "વેબસાઇટનું નામ અસલી બેંક/કંપનીની નકલ કરે છે (નકલી મળતું સરનામું)."},
    "tld": {"en": "The link uses a suspicious website ending (like .xyz, .top, .click).",
            "hi": "लिंक में संदिग्ध वेबसाइट एंडिंग है (जैसे .xyz, .top, .click)।",
            "gu": "લિંકમાં શંકાસ્પદ વેબસાઇટ અંત છે (જેમ કે .xyz, .top, .click)."},
    "http": {"en": "The link is not secure (http, not https).",
             "hi": "लिंक सुरक्षित नहीं है (https की जगह http)।",
             "gu": "લિંક સુરક્ષિત નથી (https ને બદલે http)."},
    "apk": {"en": "It asks you to download an app file (APK) which can steal your money.",
            "hi": "यह ऐप फ़ाइल (APK) डाउनलोड करने को कहता है, जो आपका पैसा चुरा सकती है।",
            "gu": "તે એપ ફાઇલ (APK) ડાઉનલોડ કરવા કહે છે, જે તમારા પૈસા ચોરી શકે છે."},
    "urgency": {"en": "It pressures you to act immediately or threatens to block something.",
                "hi": "यह तुरंत कदम उठाने का दबाव डालता है या कुछ बंद करने की धमकी देता है।",
                "gu": "તે તરત પગલું ભરવા દબાણ કરે છે અથવા કંઈક બંધ કરવાની ધમકી આપે છે."},
    "kyc": {"en": "Fake 'KYC update' message - banks do not ask for KYC through links or SMS.",
            "hi": "यह नकली 'KYC अपडेट' संदेश है - बैंक लिंक या SMS से KYC नहीं मांगते।",
            "gu": "આ નકલી 'KYC અપડેટ' સંદેશ છે - બેંકો લિંક કે SMS દ્વારા KYC માંગતી નથી."},
    "otp": {"en": "It asks you to share an OTP/PIN/password - a real bank never does.",
            "hi": "यह OTP/PIN/पासवर्ड मांगता है - असली बैंक कभी नहीं मांगता।",
            "gu": "તે OTP/PIN/પાસવર્ડ માંગે છે - અસલી બેંક ક્યારેય માંગતી નથી."},
    "collect": {"en": "UPI trick: you never need to enter your PIN to RECEIVE money. Approving a request sends money out.",
                "hi": "UPI की चाल: पैसे पाने के लिए PIN कभी नहीं डालना पड़ता। रिक्वेस्ट मंज़ूर करने से पैसे कट जाते हैं।",
                "gu": "UPI ની ચાલ: પૈસા મેળવવા માટે PIN નાખવો પડતો નથી. રિક્વેસ્ટ મંજૂર કરવાથી પૈસા કપાઈ જાય છે."},
    "prize": {"en": "Fake prize/lottery - you can't win a contest you never entered.",
              "hi": "नकली इनाम/लॉटरी - जिस प्रतियोगिता में भाग नहीं लिया उसमें जीत नहीं सकते।",
              "gu": "નકલી ઇનામ/લોટરી - જેમાં ભાગ લીધો નથી તેમાં જીતી શકાય નહીં."},
    "courier": {"en": "Fake courier/parcel message asking for a fee.",
                "hi": "नकली कूरियर/पार्सल संदेश जो शुल्क मांग रहा है।",
                "gu": "નકલી કુરિયર/પાર્સલ સંદેશ જે ફી માંગે છે."},
    "fee": {"en": "It asks for an advance/processing fee - a classic scam sign.",
            "hi": "यह एडवांस/प्रोसेसिंग फीस मांगता है - ठगी का आम संकेत।",
            "gu": "તે એડવાન્સ/પ્રોસેસિંગ ફી માંગે છે - છેતરપિંડીની સામાન્ય નિશાની."},
    "remote": {"en": "It asks you to install a remote-access app so scammers can control your phone.",
               "hi": "यह रिमोट-एक्सेस ऐप इंस्टॉल करने को कहता है ताकि ठग आपका फ़ोन चला सकें।",
               "gu": "તે રિમોટ-એક્સેસ એપ ઇન્સ્ટૉલ કરવા કહે છે જેથી ઠગ તમારો ફોન ચલાવી શકે."},
    "refund": {"en": "Refund/cashback bait with a link or contact to lure you.",
               "hi": "रिफंड/कैशबैक का लालच, साथ में लिंक या संपर्क।",
               "gu": "રિફંડ/કેશબેકનું લાલચ, સાથે લિંક કે સંપર્ક."},
    "upi_pay": {"en": "It asks you to pay money to a personal UPI ID.",
                "hi": "यह किसी निजी UPI ID पर पैसे भेजने को कहता है।",
                "gu": "તે કોઈ અંગત UPI ID પર પૈસા મોકલવા કહે છે."},
}
KEYS = [("shortener", "shortener"), ("Punycode", "lookalike"), ("Lookalike", "lookalike"), ("Suspicious domain", "tld"),
        ("not secure", "http"), ("APK", "apk"), ("Urgency", "urgency"), ("KYC", "kyc"), ("OTP", "otp"),
        ("collect", "collect"), ("prize", "prize"), ("Courier", "courier"), ("advance", "fee"),
        ("remote", "remote"), ("Refund", "refund"), ("personal UPI", "upi_pay")]
TYPE = {"red": {"en": "Likely scam", "hi": "संभावित ठगी", "gu": "સંભવિત છેતરપિંડી"},
        "amber": {"en": "Suspicious", "hi": "संदिग्ध", "gu": "શંકાસ્પદ"},
        "green": {"en": "Looks safe", "hi": "सुरक्षित लगता है", "gu": "સુરક્ષિત લાગે છે"}}
ADV = {
    "bad": {"en": ["Do not pay anything and do not click any link.", "Never share OTP, PIN or card details.",
                   "Block the sender.", "Report: call helpline 1930 or visit cybercrime.gov.in."],
            "hi": ["कोई पैसा न दें और किसी लिंक पर क्लिक न करें।", "OTP, PIN या कार्ड की जानकारी कभी साझा न करें।",
                   "भेजने वाले को ब्लॉक करें।", "रिपोर्ट करें: हेल्पलाइन 1930 पर कॉल करें या cybercrime.gov.in पर जाएँ।"],
            "gu": ["કોઈ પૈસા ન આપો અને કોઈ લિંક પર ક્લિક ન કરો.", "OTP, PIN કે કાર્ડની વિગતો ક્યારેય શેર ન કરો.",
                   "મોકલનારને બ્લૉક કરો.", "રિપોર્ટ કરો: હેલ્પલાઇન 1930 પર કૉલ કરો અથવા cybercrime.gov.in પર જાઓ."]},
    "ok": {"en": ["No obvious scam signs found, but never share your OTP or PIN with anyone.",
                  "If unsure, call your bank on the number printed on your card. Helpline: 1930."],
           "hi": ["कोई साफ़ ठगी के संकेत नहीं मिले, फिर भी OTP या PIN किसी से साझा न करें।",
                  "संदेह हो तो कार्ड पर छपे नंबर पर बैंक को कॉल करें। हेल्पलाइन: 1930।"],
           "gu": ["ઠગાઈના સ્પષ્ટ સંકેત મળ્યા નથી, છતાં OTP કે PIN કોઈને ન આપો.",
                  "શંકા હોય તો કાર્ડ પર છાપેલા નંબર પર બેંકને કૉલ કરો. હેલ્પલાઇન: 1930."]},
}
OK_REASON = {"en": "No suspicious link, payment request or OTP request was found.",
             "hi": "कोई संदिग्ध लिंक, भुगतान या OTP की मांग नहीं मिली।",
             "gu": "કોઈ શંકાસ્પદ લિંક, ચુકવણી કે OTP ની માંગ મળી નથી."}


def code_reasons(flags, lang):
    out = []
    for f in flags:
        for sub, cat in KEYS:
            if sub.lower() in f.lower():
                t = R[cat][lang]
                if t not in out:
                    out.append(t)
                break
    return out


def code_only(ca, lang, ai_unavailable=True):
    sev = ca["severity"]
    reasons = code_reasons(ca["flags"], lang)[:4] or ([OK_REASON[lang]] if sev == "green" else [])
    return {"verdict": sev, "scam_type": TYPE[sev][lang], "reasons": reasons, "red_flags_found": ca["flags"],
            "extracted": ca["extracted"], "advice": ADV["ok" if sev == "green" else "bad"][lang]}


def _merge(a, b):
    return list(dict.fromkeys((a or []) + (b or [])))


def _mime(data, declared):
    if data[:8] == b"\x89PNG\r\n\x1a\n": return "image/png"
    if data[:3] == b"\xff\xd8\xff": return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return "image/webp"
    if data[:3] == b"GIF": return "image/gif"
    return declared if declared and declared.startswith("image/") else "image/png"


def _norm_text(text):
    """Whitespace-insensitive: browsers send FormData newlines as CRLF, users add trailing spaces, etc."""
    return " ".join((text or "").split())


def _cache_path(img, text, lang):
    h = hashlib.sha256(img + b"\0" + _norm_text(text).encode() + b"\0" + lang.encode()).hexdigest()
    return CACHE / f"{h}.json"


_SAMPLE_BY_IMG = {}


def _sample_text_for(img):
    """If img is byte-identical to samples/<n>.png return samples/<n>.txt (so an image-only or text-edited sample click still hits cache)."""
    if not _SAMPLE_BY_IMG and SAMPLES.is_dir():
        for p in SAMPLES.glob("*.png"):
            t = p.with_suffix(".txt")
            if t.is_file():
                _SAMPLE_BY_IMG[hashlib.sha256(p.read_bytes()).hexdigest()] = t.read_text(encoding="utf-8")
    return _SAMPLE_BY_IMG.get(hashlib.sha256(img).hexdigest())


NO_TYPE = {"", "none", "n/a", "na", "null", "nil", "no scam", "not a scam", "-", "safe"}


def _clean_type(out):
    """Green verdicts (or an LLM 'none'/'n/a') carry no scam type: always the empty string."""
    t = str(out.get("scam_type") or "").strip()
    out["scam_type"] = "" if out.get("verdict") == "green" or t.lower().strip(" .") in NO_TYPE else t
    return out


@app.get("/api/config")
def config():
    cid = auth.client_id()
    return {"auth_required": cid is not None, "google_client_id": cid}


@app.get("/api/health")
def health():
    return {"ok": True, "gemini_key": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
            "backend": os.environ.get("LLM_BACKEND", "gemini"), "model": llm.MODEL}


@app.post("/api/check")
def check(request: Request, image: UploadFile | None = File(None), text: str = Form(""), lang: str = Form("en")):  # sync def -> runs in threadpool, blocking LLM call never stalls the event loop
    lang = lang if lang in LANGS else "en"
    text = (text or "").strip()[:MAX_TEXT]  # huge pastes: only the first part is analysed
    img = b""
    if image is not None and image.filename:
        img = image.file.read(MAX_IMG + 1)
    if not img and not text:
        raise HTTPException(400, "Provide text or an image")
    if len(img) > MAX_IMG:
        raise HTTPException(400, "Image too large (max 8MB)")
    mime = ""
    if img:
        ct = (image.content_type or "").lower()
        mime = _mime(img, ct)
        known = img[:8] == b"\x89PNG\r\n\x1a\n" or img[:3] in (b"\xff\xd8\xff", b"GIF") or (img[:4] == b"RIFF" and img[8:12] == b"WEBP")
        if known:
            try:  # truncated / corrupt images would only waste a model call and fail upstream
                from PIL import Image
                Image.open(io.BytesIO(img)).load()
            except ImportError:
                pass
            except Exception:
                raise HTTPException(400, "Could not read this image (corrupt or truncated)")
        elif ct not in ("image/heic", "image/heif"):
            raise HTTPException(400, "File must be a PNG, JPEG, WebP or GIF image")

    cp = _cache_path(img, text, lang)
    probes = [cp]
    if img:
        st = _sample_text_for(img)
        if st is not None:
            probes.append(_cache_path(img, st, lang))
    for p in probes:  # cache is read FIRST, before any analysis or LLM call
        try:
            if p.exists():
                log.info("cache hit lang=%s img=%s", lang, bool(img))
                return _clean_type({**json.loads(p.read_text()), "source": "cache"})
        except Exception:
            pass

    # cache missed -> a LIVE model call is needed. Auth mode: caller must be signed in and bring their own Gemini key.
    user_key = auth.require_user_key(request.headers) if auth.enabled() else None

    ca = checks.analyze(text)
    try:
        if user_key is None:
            res, source = llm.check(text, img or None, mime or "image/png", lang)
        else:
            res, source = llm.check(text, img or None, mime or "image/png", lang, api_key=user_key)
        ai_unavailable = False
    except llm.LLMUnavailable as e:
        res, source, ai_unavailable = None, "code", True
        log.warning("LLM unavailable, serving code-only result lang=%s img=%s: %s", lang, bool(img), e)

    if res is None:
        out = code_only(ca, lang)
        if not text and img:  # image only, nothing analysed -> be honest, never "green"
            out["verdict"] = "amber"
            out["scam_type"] = TYPE["amber"][lang]
            out["advice"] = ADV["bad"][lang]
            out["reasons"] = [{"en": "AI is unavailable, so this screenshot could not be read. Treat it with caution.",
                               "hi": "AI उपलब्ध नहीं है, इसलिए यह स्क्रीनशॉट पढ़ा नहीं जा सका। सावधानी रखें।",
                               "gu": "AI ઉપલબ્ધ નથી, તેથી આ સ્ક્રીનશૉટ વાંચી શકાયો નથી. સાવચેત રહો."}[lang]]
    else:
        final = checks.combine(ca["severity"], res["verdict"])
        out = dict(res)
        out["verdict"] = final
        out["extracted"] = {k: _merge(res["extracted"].get(k), ca["extracted"].get(k)) for k in ("urls", "phones", "upi_ids", "amounts")}
        out["red_flags_found"] = _merge(res["red_flags_found"], ca["flags"])
        if final != res["verdict"]:  # code checks overrode the AI -> use code explanations
            c = code_only(ca, lang)
            out["reasons"] = (c["reasons"] + out["reasons"])[:4]
            out["advice"] = c["advice"]
            out["scam_type"] = out["scam_type"] if res["verdict"] != "green" else c["scam_type"]
        if not out["reasons"]:
            out["reasons"] = code_reasons(ca["flags"], lang)[:4]
    _clean_type(out)
    out.update(lang=lang, ai_unavailable=ai_unavailable, source=source, code_flags=ca["flags"], code_score=ca["score"])
    if not ai_unavailable:
        try:
            CACHE.mkdir(exist_ok=True)
            cp.write_text(json.dumps(out, ensure_ascii=False))
        except OSError:
            pass
    return out


class ComplaintReq(BaseModel):
    result: dict
    lang: Literal["gu", "hi", "en"] = "en"
    details: dict | None = None

    @field_validator("result")
    @classmethod
    def _has_verdict(cls, v):
        if v.get("verdict") not in ("red", "amber", "green"):
            raise ValueError("result must be an /api/check result (verdict red|amber|green)")
        return v


@app.post("/api/complaint")
def complaint_endpoint(req: ComplaintReq, request: Request):
    """Draft a cybercrime-portal complaint. Stateless: with personal details present nothing is cached or logged."""
    details = cmp.clean_details(req.details)
    cdir = CACHE / "complaints"
    cp = cdir / f"{cmp.cache_key(req.result, req.lang)}.json"
    if not details and cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            pass
    user_key = auth.require_user_key(request.headers) if auth.enabled() else None  # live draft needed
    out = cmp.build(req.result, req.lang, details, api_key=user_key)
    log.info("complaint lang=%s source=%s has_details=%s", req.lang, out["source"], bool(details))
    if not details and out["source"] != "template":
        try:
            cdir.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return out


# /samples/* served statically; registered before the web/ catch-all below. Tolerates missing dir.
app.mount("/samples", StaticFiles(directory=str(SAMPLES), check_dir=False), name="samples")


@app.get("/{path:path}")
def static(path: str = ""):
    if path.startswith("api/"):
        raise HTTPException(404)
    base = WEB.resolve()
    f = (base / (path or "index.html")).resolve()
    if f.is_dir():
        f = f / "index.html"
    if base in f.parents and f.is_file():
        return FileResponse(f)
    if not WEB.exists() or not (base / "index.html").exists():
        return JSONResponse({"message": "Thagi Pakdo API is running. POST /api/check. web/index.html not found yet."})
    raise HTTPException(404)
