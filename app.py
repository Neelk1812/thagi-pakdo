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
        if isinstance(rec.msg, str):
            m = rec.getMessage()
            s = llm.scrub(m)
            if s != m:  # only touch records that actually contain a secret (leave e.g. uvicorn's structured args alone)
                rec.msg, rec.args = s, ()
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
MAX_IMG = 4 * 1024 * 1024
MAX_BODY = 4 * 1024 * 1024  # whole request; also keeps us under Vercel's ~4.5 MB function body limit
MAX_TEXT = 5000
LANGS = ("gu", "hi", "en")

import collections, threading, time

TOO_LARGE = {"en": "This is too big to check. Please use a smaller screenshot (under 4 MB) or paste the text.",
             "hi": "यह जाँच के लिए बहुत बड़ा है। कृपया 4 MB से छोटा स्क्रीनशॉट इस्तेमाल करें या टेक्स्ट पेस्ट करें।",
             "gu": "આ તપાસ માટે ખૂબ મોટું છે. કૃપા કરીને 4 MB થી નાનો સ્ક્રીનશૉટ વાપરો અથવા ટેક્સ્ટ પેસ્ટ કરો."}
RATE_MSG = {"en": "You're checking too fast. Please wait {s} seconds and try again.",
            "hi": "आप बहुत तेज़ी से जाँच रहे हैं। कृपया {s} सेकंड रुककर फिर कोशिश करें।",
            "gu": "તમે બહુ ઝડપથી તપાસ કરી રહ્યા છો. કૃપા કરીને {s} સેકન્ડ રાહ જુઓ અને ફરી પ્રયત્ન કરો."}


class TooLarge(HTTPException):
    def __init__(self, lang="en"):
        super().__init__(413, TOO_LARGE.get(lang, TOO_LARGE["en"]))


class BodyLimit:
    """Pure-ASGI guard: 413 as soon as Content-Length (or the streamed body) exceeds MAX_BODY. Only POST /api/*."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH") or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        cl = dict(scope["headers"]).get(b"content-length", b"")
        if cl.isdigit() and int(cl) > MAX_BODY:
            return await JSONResponse({"error": "too_large", "message": TOO_LARGE["en"]}, status_code=413)(scope, receive, send)
        got = 0

        async def limited():
            nonlocal got
            msg = await receive()
            if msg["type"] == "http.request":
                got += len(msg.get("body", b""))
                if got > MAX_BODY:
                    raise TooLarge()
            return msg
        await self.app(scope, limited, send)


class RateLimiter:
    """Per-IP sliding window, in memory, bounded (idle IPs are pruned)."""
    def __init__(self, window=60.0, max_keys=5000):
        self.window, self.max_keys, self.hits, self.lock, self.n = window, max_keys, {}, threading.Lock(), 0

    def hit(self, bucket, ip, limit):
        """Record a request; return 0 if allowed, else seconds until the oldest hit expires."""
        if limit <= 0:
            return 0
        now, key = time.monotonic(), (bucket, ip)
        with self.lock:
            self.n += 1
            if self.n % 200 == 0 or len(self.hits) > self.max_keys:
                for k in [k for k, d in self.hits.items() if not d or now - d[-1] > self.window]:
                    del self.hits[k]
                if len(self.hits) > self.max_keys:  # still huge: drop the oldest-active half
                    for k in sorted(self.hits, key=lambda k: self.hits[k][-1])[: len(self.hits) // 2]:
                        del self.hits[k]
            d = self.hits.setdefault(key, collections.deque())
            while d and now - d[0] >= self.window:
                d.popleft()
            if len(d) >= limit:
                return max(1, int(self.window - (now - d[0])) + 1)
            d.append(now)
            return 0


LIMITER = RateLimiter()


def client_ip(request):
    xff = request.headers.get("x-forwarded-for", "")
    return (xff.split(",")[0].strip() if xff else "") or (request.client.host if request.client else "unknown")


def rate_limited(request, bucket, lang):
    """JSONResponse(429) if this IP is over the limit for `bucket`, else None. Call only AFTER the cache lookup."""
    limit = int(os.environ.get("RATE_LIMIT_CHECK" if bucket == "check" else "RATE_LIMIT_COMPLAINT", "20" if bucket == "check" else "10"))
    wait = LIMITER.hit(bucket, client_ip(request), limit)
    if not wait:
        return None
    return JSONResponse({"error": "rate_limited", "message": RATE_MSG.get(lang, RATE_MSG["en"]).format(s=wait), "retry_after": wait},
                        status_code=429, headers={"Retry-After": str(wait)})


app = FastAPI(title="Thagi Pakdo")
app.add_middleware(BodyLimit)  # added before CORS => inside it, so 413s still carry CORS headers
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])  # incl. Authorization, X-Gemini-Key


@app.exception_handler(TooLarge)
async def _too_large(request, exc):
    return JSONResponse({"error": "too_large", "message": exc.detail}, status_code=413)


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
    "digital_arrest": {"en": "'Digital arrest' is a scam - no police, CBI, customs or court ever arrests anyone over a call or video call.",
                       "hi": "'डिजिटल अरेस्ट' ठगी है - पुलिस, CBI, कस्टम या कोर्ट कभी फ़ोन या वीडियो कॉल पर गिरफ्तार नहीं करते।",
                       "gu": "'ડિજિટલ અરેસ્ટ' છેતરપિંડી છે - પોલીસ, CBI, કસ્ટમ કે કોર્ટ ક્યારેય ફોન કે વીડિયો કૉલ પર ધરપકડ કરતા નથી."},
    "impersonation": {"en": "Someone claims to be police/CBI/customs/court and threatens arrest or a case to scare you.",
                      "hi": "कोई खुद को पुलिस/CBI/कस्टम/कोर्ट बताकर गिरफ्तारी या केस की धमकी देकर डरा रहा है।",
                      "gu": "કોઈ પોતાને પોલીસ/CBI/કસ્ટમ/કોર્ટ ગણાવી ધરપકડ કે કેસની ધમકી આપીને ડરાવે છે."},
    "coerce": {"en": "They want you to stay on a call or video call so you cannot think or ask anyone.",
               "hi": "वे आपको कॉल या वीडियो कॉल पर बनाए रखना चाहते हैं ताकि आप सोच न सकें या किसी से पूछ न सकें।",
               "gu": "તેઓ તમને કૉલ કે વીડિયો કૉલ પર રાખવા માંગે છે જેથી તમે વિચારી ન શકો કે કોઈને પૂછી ન શકો."},
    "secret": {"en": "They tell you to keep it secret - scammers do this so family cannot warn you.",
               "hi": "वे इसे गुप्त रखने को कहते हैं - ठग ऐसा इसलिए करते हैं कि घरवाले आपको रोक न सकें।",
               "gu": "તેઓ આ વાત ગુપ્ત રાખવા કહે છે - ઠગ એટલા માટે કે ઘરના લોકો તમને રોકી ન શકે."},
    "safe_acct": {"en": "No bank, RBI or police ever asks you to move money to a 'safe account'. This is a scam.",
                  "hi": "कोई बैंक, RBI या पुलिस कभी 'सुरक्षित खाते' में पैसे ट्रांसफर करने को नहीं कहती। यह ठगी है।",
                  "gu": "કોઈ બેંક, RBI કે પોલીસ ક્યારેય 'સુરક્ષિત ખાતા'માં પૈસા ટ્રાન્સફર કરવા કહેતી નથી. આ છેતરપિંડી છે."},
    "verify_tx": {"en": "Asking you to send money 'for verification' or 'investigation' with a promise to refund it is a scam.",
                  "hi": "'सत्यापन' या 'जांच' के नाम पर पैसे भेजने और वापस करने का वादा ठगी है।",
                  "gu": "'ચકાસણી' કે 'તપાસ' નામે પૈસા મોકલવા અને પાછા આપવાનું વચન એ છેતરપિંડી છે."},
    "card": {"en": "It asks for your ATM PIN, CVV or card details - a real bank never does.",
             "hi": "यह आपका ATM पिन, CVV या कार्ड की जानकारी मांगता है - असली बैंक कभी नहीं मांगता।",
             "gu": "તે તમારો ATM પિન, CVV કે કાર્ડની વિગતો માંગે છે - અસલી બેંક ક્યારેય માંગતી નથી."},
    "job_task": {"en": "Fake job/task scam: real employers never pay per YouTube like or task, or ask you to deposit money to unlock earnings.",
                 "hi": "नकली जॉब/टास्क ठगी: असली कंपनी लाइक या टास्क के पैसे नहीं देती और कमाई अनलॉक करने के लिए पैसे जमा नहीं करवाती।",
                 "gu": "નકલી જૉબ/ટાસ્ક છેતરપિંડી: અસલી કંપની લાઈક કે ટાસ્કના પૈસા આપતી નથી અને કમાણી અનલૉક કરવા પૈસા જમા કરાવતી નથી."},
    "loan_threat": {"en": "Loan-app style blackmail: they threaten to send your photos or contacts to family and shame you. Do not pay under threat; report it.",
                    "hi": "लोन ऐप जैसी धमकी: वे आपकी फोटो या कॉन्टैक्ट परिवार को भेजकर बदनाम करने की धमकी देते हैं। धमकी में आकर पैसे न दें; रिपोर्ट करें।",
                    "gu": "લોન ઍપ જેવી ધમકી: તેઓ તમારા ફોટા કે કોન્ટેક્ટ પરિવારને મોકલી બદનામ કરવાની ધમકી આપે છે. ધમકીથી પૈસા ન આપો; રિપોર્ટ કરો."},
    "sextortion": {"en": "Blackmail: they threaten to leak your private video/photos unless you pay. Do not pay; stop replying, keep the evidence and report at 1930.",
                   "hi": "ब्लैकमेल: वे पैसे न देने पर आपकी निजी वीडियो/फोटो लीक करने की धमकी देते हैं। पैसे न दें; जवाब देना बंद करें, सबूत रखें और 1930 पर रिपोर्ट करें।",
                   "gu": "બ્લૅકમેલ: પૈસા ન આપો તો તમારો ખાનગી વીડિયો/ફોટા લીક કરવાની ધમકી આપે છે. પૈસા ન આપો; જવાબ આપવાનું બંધ કરો, પુરાવા રાખો અને 1930 પર રિપોર્ટ કરો."},
    "officer_pay": {"en": "A so-called officer on a video call/Skype asks you to send money - no real officer ever does this.",
                    "hi": "वीडियो कॉल/Skype पर कथित अधिकारी पैसे भेजने को कह रहा है - असली अधिकारी कभी ऐसा नहीं करता।",
                    "gu": "વીડિયો કૉલ/Skype પર કહેવાતા અધિકારી પૈસા મોકલવા કહે છે - અસલી અધિકારી ક્યારેય આવું કરતા નથી."},
    "case_pay": {"en": "They say a case is registered against you or your SIM and ask for money to close it. Police never settle cases by phone payment.",
                 "hi": "वे कहते हैं कि आपके या आपके सिम के खिलाफ केस दर्ज है और केस बंद करने के लिए पैसे मांगते हैं। पुलिस फ़ोन पर पैसे लेकर केस बंद नहीं करती।",
                 "gu": "તેઓ કહે છે કે તમારા કે તમારા સિમ સામે કેસ નોંધાયો છે અને કેસ બંધ કરવા પૈસા માંગે છે. પોલીસ ફોન પર પૈસા લઈને કેસ બંધ કરતી નથી."},
    "upi_pay": {"en": "It asks you to pay money to a personal UPI ID.",
                "hi": "यह किसी निजी UPI ID पर पैसे भेजने को कहता है।",
                "gu": "તે કોઈ અંગત UPI ID પર પૈસા મોકલવા કહે છે."},
}
KEYS = [("pay-to-earn", "job_task"), ("Loan-app", "loan_threat"), ("Blackmail threat", "sextortion"), ("Officer on a video", "officer_pay"),
        ("registered against you and asks payment", "case_pay"), ("digital arrest", "digital_arrest"), ("threatens arrest", "impersonation"), ("stay on a", "coerce"),
        ("keep it secret", "secret"), ("safe'/RBI", "safe_acct"), ("for verification/investigation", "verify_tx"),
        ("ATM PIN, CVV", "card"),  # new flags first: their labels also contain old keys (e.g. "Refund", "OTP")
        ("shortener", "shortener"), ("Punycode", "lookalike"), ("Lookalike", "lookalike"), ("Suspicious domain", "tld"),
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
UNCHECKED = {"en": "We couldn't fully check this message. Be careful: don't click links, pay, or share OTP/PIN until you verify with the sender or your bank.",
             "hi": "हम इस संदेश की पूरी जाँच नहीं कर पाए। सावधान रहें: भेजने वाले या अपने बैंक से पुष्टि होने तक लिंक पर क्लिक न करें, पैसे न दें और OTP/PIN साझा न करें।",
             "gu": "અમે આ સંદેશની પૂરી તપાસ કરી શક્યા નથી. સાવચેત રહો: મોકલનાર કે તમારી બેંક સાથે ખાતરી કર્યા વિના લિંક પર ક્લિક ન કરો, પૈસા ન આપો અને OTP/PIN શેર ન કરો."}
ADV["unchecked"] = {"en": ["Do not click links, pay or share OTP/PIN until you verify with the sender or your bank.",
                          "If unsure, call your bank on the number printed on your card. Report scams: helpline 1930 or cybercrime.gov.in."],
                    "hi": ["भेजने वाले या अपने बैंक से पुष्टि होने तक लिंक पर क्लिक न करें, पैसे न दें और OTP/PIN साझा न करें।",
                           "संदेह हो तो कार्ड पर छपे नंबर पर बैंक को कॉल करें। ठगी की रिपोर्ट: हेल्पलाइन 1930 या cybercrime.gov.in।"],
                    "gu": ["મોકલનાર કે તમારી બેંક સાથે ખાતરી કર્યા વિના લિંક પર ક્લિક ન કરો, પૈસા ન આપો અને OTP/PIN શેર ન કરો.",
                           "શંકા હોય તો કાર્ડ પર છાપેલા નંબર પર બેંકને કૉલ કરો. છેતરપિંડીની જાણ: હેલ્પલાઇન 1930 અથવા cybercrime.gov.in."]}
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
        raise TooLarge(lang)
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

    limited = rate_limited(request, "check", lang)  # after the cache lookup: cached/sample hits are never limited or counted
    if limited:
        return limited
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
        if ca["severity"] == "green":  # AI did not run AND the code rules found nothing: fail open to AMBER, never "looks safe"
            out.update(verdict="amber", scam_type=TYPE["amber"][lang], reasons=[UNCHECKED[lang]], advice=ADV["unchecked"][lang])
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
            CACHE.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(out, ensure_ascii=False))
        except OSError as e:  # read-only / unwritable filesystem (e.g. container): serve the result, just don't cache it
            log.warning("cache write skipped (%s)", type(e).__name__)
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
    limited = rate_limited(request, "complaint", req.lang)
    if limited:
        return limited
    user_key = auth.require_user_key(request.headers) if auth.enabled() else None  # live draft needed
    out = cmp.build(req.result, req.lang, details, api_key=user_key)
    log.info("complaint lang=%s source=%s has_details=%s", req.lang, out["source"], bool(details))
    if not details and out["source"] != "template":
        try:
            cdir.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            log.warning("complaint cache write skipped (%s)", type(e).__name__)
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
