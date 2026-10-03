"""Plain-code scam checks (no LLM). analyze(text) -> dict."""
import re
from urllib.parse import urlparse

SEV = {"green": 0, "amber": 1, "red": 2}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "cutt.ly", "is.gd", "rb.gy", "goo.gl", "ow.ly", "shorturl.at",
              "tiny.cc", "rebrand.ly", "bitly.com", "s.id", "t.ly", "v.gd", "buff.ly", "lnkd.in", "wa.me/message"}
BAD_TLDS = {"xyz", "top", "click", "cc", "icu", "online", "site", "buzz", "club", "vip", "live", "shop", "link", "work", "cfd", "sbs"}
BRANDS = ["sbi", "hdfc", "icici", "axis", "kotak", "paytm", "phonepe", "npci", "irctc", "amazon", "flipkart",
          "indiapost", "pnb", "gpay", "bhim", "airtel", "jio", "uidai", "aadhaar", "incometax", "epfo"]
LEGIT = ["sbi.co.in", "onlinesbi.sbi", "sbi.bank.in", "hdfcbank.com", "icicibank.com", "axisbank.com", "kotak.com",
         "pnbindia.in", "paytm.com", "phonepe.com", "npci.org.in", "irctc.co.in", "amazon.in", "amazon.com",
         "flipkart.com", "indiapost.gov.in", "airtel.in", "jio.com", "uidai.gov.in", "incometax.gov.in",
         "epfindia.gov.in", "pay.google.com", "bhimupi.org.in", "wa.me"]

TLD = r"com|in|net|org|co|xyz|top|click|cc|icu|online|site|ly|me|gl|is|link|info|biz|app|live|shop|vip|club|buzz|work|cfd|sbs|gov|bank|sbi|cc"
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"'()]+|(?<![@\w.\-])(?:[a-z0-9][a-z0-9\-]*\.)+(?:%s)\b(?:/[^\s<>\"'()]*)?" % TLD, re.I)
UPI_RE = re.compile(r"(?<![\w.\-])[\w.\-]{2,}@[a-zA-Z]{2,}\b(?!\.[a-zA-Z])")
PHONE_RE = re.compile(r"(?<![\d])(?:\+?91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}(?!\d)")
AMOUNT_RE = re.compile(r"(?:Rs\.?|INR|₹)\s?\d[\d,]*(?:\.\d+)?(?:/-)?|\d[\d,]*(?:\.\d+)?\s?(?:rupees|/-)", re.I)

URGENCY = re.compile(r"urgent|immediately|right now|within\s+\d+\s*(?:hours?|hrs?|mins?|minutes?)|last\s+(?:chance|day)|"
                     r"will be (?:blocked|suspended|closed|deactivated|disabled)|(?:account|card|sim|number).{0,20}(?:blocked|suspended)|"
                     r"will expire|has expired|expires? today|today only|तुरंत|जल्दी|तत्काल|તાત્કાલિક|તરત|ઝડપથી", re.I)
KYC = re.compile(r"\bkyc\b|केवाईसी|કેવાયસી|pan\s*(?:card)?\s*(?:update|verif)|aadhaar\s*(?:update|verif)", re.I)
KYC_ACT = re.compile(r"update|verif|pending|expire|complete|submit|suspend|block|अपडेट|અપડેટ", re.I)
OTP_WORD = re.compile(r"\botp\b|\bpin\b|\bcvv\b|ओटीपी|ઓટીપી|password", re.I)
OTP_ASK = re.compile(r"\b(?:share|send|forward|tell|give|provide|read out|reply|confirm|enter|submit|batao|bhejo)\b|बताएं|भेजें|बताओ|શેર|મોકલો", re.I)
NEGATION = re.compile(r"\b(?:do not|don'?t|dont|never|not to|do NOT|avoid|beware)\b|मत|न करें|ન કરો|નહીં|ના કરો", re.I)
COLLECT = re.compile(r"collect\s*request|payment\s*request|request(?:ed)?\s*(?:money|payment)|approve\s+(?:the\s+)?request|"
                     r"accept\s+(?:the\s+)?request|enter\s+(?:your\s+)?(?:upi\s*)?pin\s+to\s+(?:receive|get|credit|claim)|"
                     r"(?:upi\s*)?pin\s+(?:is\s+)?(?:required|needed)\s+to\s+(?:receive|get|credit)|scan\s+(?:this\s+)?qr.{0,30}(?:receive|get|refund)", re.I)
PRIZE = re.compile(r"lottery|lucky\s*draw|jackpot|\bkbc\b|you(?:'ve| have)?\s+(?:won|been selected)|\bwinner\b|\bprize\b|"
                   r"congratulations.{0,60}(?:won|win|prize|reward|gift)|लॉटरी|इनाम|જીત્યા|લોટરી|ઇનામ", re.I)
COURIER_W = re.compile(r"courier|parcel|package|shipment|consignment|delivery|india\s*post|dtdc|fedex|blue\s*dart|delhivery|कूरियर|પાર્સલ|કુરિયર", re.I)
COURIER_FEE = re.compile(r"fee|charge|pay|customs|redeliver|re-?deliver|reschedule|address.{0,15}(?:incomplete|invalid|wrong)|on hold|held|शुल्क|ચાર્જ|ફી", re.I)
REMOTE = re.compile(r"anydesk|teamviewer|quick\s*support|rustdesk|screen\s*share", re.I)
REFUND = re.compile(r"refund|cashback|reward points|रिफंड|રિફંડ", re.I)
FEE_ASK = re.compile(r"(?:processing|registration|advance|release|clearance|customs)\s+(?:fee|charge)", re.I)


def _reg_domain(host):
    return host.lower().strip(".")


def _norm(s):
    return s.translate(str.maketrans("01345$", "oleass")) + "|" + s.translate(str.maketrans("01345$", "oieass"))


def _host(url):
    u = url if re.match(r"https?://", url, re.I) else "http://" + url
    try:
        return (urlparse(u).hostname or "").lower()
    except ValueError:
        return ""


def _clean_url(u):
    return u.rstrip(".,;:!?)]}>\"'")


def extract(text):
    urls = []
    for m in URL_RE.findall(text):
        m = _clean_url(m)
        if m and m not in urls:
            urls.append(m)
    upis = []
    for m in UPI_RE.findall(text):
        if m not in upis:
            upis.append(m)
    phones = []
    for m in PHONE_RE.findall(text):
        m = m.strip()
        if m not in phones:
            phones.append(m)
    amounts = []
    for m in AMOUNT_RE.findall(text):
        m = m.strip()
        if m not in amounts:
            amounts.append(m)
    return {"urls": urls, "phones": phones, "upi_ids": upis, "amounts": amounts}


def _otp_request(text):
    for sent in re.split(r"[.!?\n।]+", text):
        if OTP_WORD.search(sent) and OTP_ASK.search(sent) and not NEGATION.search(sent):
            return True
    return False


def analyze(text):
    text = text or ""
    ex = extract(text)
    flags = []  # (weight, label)

    def add(w, label):
        flags.append((w, label))

    for u in ex["urls"]:
        host = _host(u)
        if not host:
            continue
        low = u.lower()
        short = next((s for s in SHORTENERS if host == s.split("/")[0] and (("/" not in s) or s in low)), None)
        if short:
            add(2, f"URL shortener hides the real link ({short.split('/')[0]})")
        if "xn--" in host:
            add(3, f"Punycode/lookalike domain ({host})")
        tld = host.rsplit(".", 1)[-1]
        if tld in BAD_TLDS:
            add(2, f"Suspicious domain ending .{tld} ({host})")
        if low.startswith("http://"):
            add(1, f"Link is not secure (http): {host}")
        if low.endswith(".apk"):
            add(3, "Link downloads an APK app file")
        legit = any(host == d or host.endswith("." + d) for d in LEGIT)
        if not legit and "xn--" not in host:
            labels_str = host
            for b in BRANDS:
                if b in labels_str or b in _norm(labels_str):
                    add(3, f"Lookalike domain pretending to be '{b}' ({host})")
                    break
    if URGENCY.search(text):
        add(1, "Urgency / threat words (pressure to act fast)")
    if KYC.search(text) and KYC_ACT.search(text):
        add(2, "KYC update request")
        if ex["urls"]:
            add(3, "KYC update with a link (classic bank-KYC scam)")
    if _otp_request(text) and not COLLECT.search(text):
        add(3, "Asks you to share/enter OTP, PIN or password")
    if COLLECT.search(text):
        add(3, "UPI collect request / 'enter PIN to receive money' trick")
    if PRIZE.search(text):
        add(3, "Fake prize / lottery pattern")
    if COURIER_W.search(text) and COURIER_FEE.search(text) and (ex["amounts"] or re.search(r"fee|charge|pay|customs|शुल्क|ચાર્જ|ફી", text, re.I)):
        add(3, "Courier/parcel fee scam pattern")
    if FEE_ASK.search(text):
        add(2, "Asks for an advance/processing fee")
    if REMOTE.search(text):
        add(3, "Asks to install a remote-access app")
    if REFUND.search(text) and (ex["upi_ids"] or ex["urls"] or ex["phones"]):
        add(1, "Refund/cashback bait with a contact or link")
    if ex["upi_ids"] and re.search(r"\b(?:pay|send|transfer)\b", text, re.I) and ex["amounts"]:
        add(1, "Asks for payment to a personal UPI ID")

    seen, labels = set(), []
    for w, l in flags:
        if l not in seen:
            seen.add(l)
            labels.append((w, l))
    total = sum(w for w, _ in labels)
    strong = any(w >= 3 for w, _ in labels)
    score = min(100, total * 20)
    sev = "red" if (strong or total >= 4) else "amber" if total >= 1 else "green"
    return {"score": score, "severity": sev, "flags": [l for _, l in labels], "strong": strong, "extracted": ex}


def combine(code_severity, llm_verdict):
    """Final severity = max(code, llm). Never lower than code severity."""
    a = code_severity if code_severity in SEV else "green"
    b = llm_verdict if llm_verdict in SEV else "green"
    return a if SEV[a] >= SEV[b] else b
