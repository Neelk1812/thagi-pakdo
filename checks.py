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
NEGATION = re.compile(r"\b(?:do not|don'?t|dont|never|not to|do NOT|avoid|beware|mat|nahi|nahin|kabhi)\b|मत|न करें|ન કરો|નહીં|ના કરો", re.I)
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

# ---- authority impersonation / "digital arrest" / safe-account / card-detail scams (en, Hinglish, hi, gu) ----
ADDRESSES_YOU = re.compile(r"\b(?:you|your|yours|aap|aapke|aapki|aapka|tum|tumhare|tumhari)\b|आप|तुम|तुम्हारे|તમારા|તમારી|તમારું|તમને|તમે", re.I)
_SENT = re.compile(r"[.!?\n।]+")
# awareness / warning sentences ("Beware: digital arrest is a scam", "TRAI never calls...") must not trigger the strong phrases
WARN_CUE = re.compile(r"\b(?:scams?|beware|aware(?:ness)?|never|fake calls?|ignore such|report such)\b|सावधान|जागरूक|ठगी से|ક્યારેય|સાવધ|જાગૃત|कभी", re.I)

_DA = (r"digital\s*arrest|arrest\s*warrant|money\s*laundering|डिजिटल\s*(?:अरेस्ट|गिरफ्तार\w*)|गिरफ्तारी\s*वारंट|मनी\s*लॉन्ड्रिंग|"
       r"ડિજિટલ\s*(?:અરેસ્ટ|ધરપકડ)|ધરપકડ\s*વોરંટ|મની\s*લોન્ડરિંગ")
_ITEM_EN = r"(?:drugs?|narcotics?|ganja|mdma|cocaine|contraband|illegal\s+(?:items?|goods?|substances?)|fake\s+passports?|counterfeit)"
_PARCEL_EN = r"(?:parcel|package|courier|consignment|shipment)"
DIGITAL_ARREST = re.compile(
    r"(?:%s)|"
    r"%s\b.{0,50}\b%s|\b%s\b.{0,50}\b%s|"
    r"(?:पार्सल|कूरियर).{0,40}(?:ड्रग|नशीले|अवैध|गैरकानूनी|नार्कोटिक)|(?:ड्रग|नार्कोटिक).{0,40}(?:पार्सल|कूरियर)|"
    r"(?:પાર્સલ|કુરિયર).{0,40}(?:ડ્રગ|નશીલ|ગેરકાયદે|ગેરકાયદેસર|નાર્કોટિક)|(?:ડ્રગ|નાર્કોટિક).{0,40}(?:પાર્સલ|કુરિયર)|"
    r"\btrai\b.{0,80}(?:disconnect|block|suspend|terminat|deactivat|\bband\b|bandh)|(?:disconnect|block|suspend|terminat|deactivat).{0,60}\btrai\b|"
    r"ट्राई.{0,80}(?:बंद|ब्लॉक|डिस्कनेक्ट)|ટ્રાઈ.{0,80}(?:બંધ|બ્લૉક|બ્લોક|ડિસ્કનેક્ટ)|"
    r"aadhaa?r\b.{0,50}(?:linked|link|connected|attached|use[d]?).{0,60}(?:illegal|money\s*laundering|crime|criminal|case|drugs?|terror|fraud|sim\s*cards?)|"
    r"आधार.{0,60}(?:अवैध|मनी\s*लॉन्ड्रिंग|अपराध|केस|ड्रग)|આધાર.{0,60}(?:ગેરકાયદે|મની\s*લોન્ડરિંગ|ગુના|કેસ|ડ્રગ)"
    % (_DA, _PARCEL_EN, _ITEM_EN, _ITEM_EN, _PARCEL_EN), re.I)
_NEG_ITEM = re.compile(r"\b(?:no|not|without|nahi|nahin)\b|नहीं|નથી|(?<![\u0A80-\u0AFF])નહીં", re.I)
AUTHORITY = re.compile(r"\bcbi\b|\bncb\b|narcotics|cyber\s*crime\s*(?:branch|cell|police|department)|crime\s*branch|customs\s+(?:officer|department|official)|"
                       r"\btrai\b|enforcement\s+directorate|\bED\s+(?:officer|case|notice)|\bpolice\b|\bcourt\b|\bwarrant\b|\bcustoms?\s+office|"
                       r"सीबीआई|पुलिस|कस्टम|ट्राई|कोर्ट|वारंट|नारकोटिक्स|साइबर\s*क्राइम|સીબીઆઈ|પોલીસ|કસ્ટમ|ટ્રાઈ|કોર્ટ|વોરંટ|નાર્કોટિક્સ|સાયબર\s*ક્રાઇમ", re.I)
LEGAL_THREAT = re.compile(r"arrest|\bcase\b|\bfir\b|illegal|money\s*laundering|\bdrugs?\b|narcotic|contraband|legal\s+action|disconnect(?:ed)?|"
                          r"involved\s+in|under\s+investigation|summons|गिरफ्तार|मामला|केस|अवैध|ड्रग|ધરપકડ|કેસ|ગેરકાયદે|ડ્રગ", re.I)
COERCE = re.compile(
    r"do\s*n[o']?t\s+(?:disconnect|cut|hang\s*up|end)\s+(?:the\s+|this\s+)?(?:video\s+)?call|stay\s+(?:on|connected\s+(?:on|to))\s+(?:the\s+|this\s+)?(?:video\s+)?(?:call|line)|"
    r"keep\s+(?:the\s+|this\s+)?(?:video\s+)?call\s+(?:on|connected)|(?:skype|whatsapp\s+video|video)\s+call.{0,50}(?:officer|police|cbi|court|verification|interrogation|statement|investigation)|"
    r"(?:officer|police|cbi|court|investigation).{0,50}(?:skype|whatsapp\s+video|video)\s+call|"
    r"call\s+(?:mat\s+|na\s+)(?:kaat\w*|katna|disconnect\w*)|call\s+disconnect\s+(?:mat|na)\b|video\s+call\s+(?:par|pe)\s+(?:rahiye|rahein|bane\s+rahe\w*|aaiye|aayiye)|"
    r"कॉल\s*(?:मत\s*काट\w*|न\s*काट\w*|डिस्कनेक्ट\s*न\w*)|वीडियो\s*कॉल\s*पर\s*(?:बने\s*रहें|रहें|आएं|आइए)|"
    r"કૉલ?\s*(?:કટ|ડિસ્કનેક્ટ)\s*(?:ન|ના)\s*કર\w*|વિડિયો\s*કૉલ?\s*પર\s*(?:રહો|રહેજો|આવો)", re.I)
SECRECY = re.compile(r"(?:do\s*n[o']?t|never)\s+tell\s+(?:this\s+to\s+)?(?:anyone|anybody|any\s*one|your\s+family)|keep\s+(?:this|it)\s+(?:a\s+)?(?:secret|confidential)|"
                     r"kisi\s+ko\s+(?:bhi\s+)?(?:mat\s+)?bata\w*|किसी\s+को\s+(?:भी\s+)?(?:न|मत)\s+बता\w*|કોઈને\s+(?:પણ\s+)?(?:કહેતા|કહેશો|જણાવતા|જણાવશો)\s*(?:નહીં|નહિ|ના)?", re.I)
_MOVE = r"(?:transfer|send|deposit|pay|move|shift|ट्रांसफर|जमा|भेज\w*|ટ્રાન્સફર|જમા|મોકલ\w*|bhej\w*|bhejo|transfer\s+kar\w*)"
SAFE_ACCT = re.compile(r"safe\s+account|rbi\s+(?:safe\s+|secure\s+)?(?:account|escrow)|rbi\s+ke\s+account|सुरक्षित\s+खाते|आरबीआई.{0,15}खाते|"
                       r"સુરક્ષિત\s+ખાતા|આરબીઆઈ.{0,15}ખાતા", re.I)
VERIFY_TRANSFER = re.compile(
    r"\b(?:transfer|send|deposit|pay)\b.{0,60}\b(?:to\s+verify|for\s+verification|for\s+investigation|verification\s+purposes?|for\s+(?:the\s+)?inquiry|for\s+(?:the\s+)?audit)|"
    r"refund(?:able|ed)?\s+(?:back\s+)?(?:after|post|once)\s+(?:the\s+)?(?:verification|investigation|inquiry)|"
    r"(?:will\s+be|is|shall\s+be)\s+(?:returned|refunded|credited\s+back)\s+(?:after|post|once)\s+(?:the\s+)?(?:verification|investigation|inquiry)|"
    r"(?:paise|amount|raashi|rupay\w*|money).{0,40}(?:transfer|bhej\w*|jama).{0,40}(?:verification|jaanch|investigation)|verification\s+ke\s+(?:liye|baad).{0,40}(?:transfer|bhej\w*|wapas|vapas)|"
    r"(?:सत्यापन|जांच|जाँच|वेरिफिकेशन).{0,40}(?:ट्रांसफर|जमा|भेज)|(?:ट्रांसफर|जमा|भेज).{0,40}(?:सत्यापन|जांच|जाँच|वेरिफिकेशन)|"
    r"(?:सत्यापन|जांच|जाँच|वेरिफिकेशन)\s*के\s*बाद.{0,25}(?:वापस|रिफंड|लौटा)|"
    r"(?:ચકાસણી|તપાસ|વેરિફિકેશન).{0,40}(?:ટ્રાન્સફર|જમા|મોકલ)|(?:ટ્રાન્સફર|જમા|મોકલ).{0,40}(?:ચકાસણી|તપાસ|વેરિફિકેશન)|"
    r"(?:ચકાસણી|તપાસ|વેરિફિકેશન)\s*(?:પછી|બાદ).{0,25}(?:પરત|રિફંડ)", re.I)
CARD_ITEM = re.compile(r"\batm\s*pin\b|\bcvv\b|\bcvc\b|card\s*(?:number|no\b|details|expiry|pin)|expiry\s*date|debit\s*card|credit\s*card|\bcard\s+ka\s+\w+|"
                       r"एटीएम\s*पिन|सीवीवी|कार्ड\s*(?:नंबर|की\s*जानकारी|विवरण|डिटेल\w*|एक्सपायरी)|समाप्ति\s*तिथि|"
                       r"એટીએમ\s*પિન|સીવીવી|કાર્ડ\s*(?:નંબર|ની\s*વિગત\w*|ડિટેલ\w*|એક્સપાયરી)|એક્સપાયરી", re.I)
CARD_VERB_EN = re.compile(r"\b(?:share|send|give|tell|provide|read\s*out|reply|confirm|enter|submit|verify|update|batao|bataiye|bataye|bhejo|bhej|dijiye)\b", re.I)
CARD_VERB_IN = re.compile(r"बताएं|बताइए|बताओ|बता\s*दीजिए|भेजें|भेजिए|भेजो|दीजिए|साझा|शेयर|दर्ज|જણાવો|જણાવ|આપો|આપજો|કહો|મોકલો|શેર|દાખલ|નાખો", re.I)
NEG_IN = re.compile(r"\b(?:mat|nahi|nahin|kabhi)\b|मत|(?<![\u0900-\u097F])न\s+(?:करें|कीजिए|बताएं|बताइए|बताओ|दें|भेजें|शेयर|साझा)|नहीं|कभी|"
                    r"(?<![\u0A80-\u0AFF])(?:ન|ના)\s*(?:કરો|આપો|જણાવો|કહો|મોકલો)|નહીં(?![\u0A80-\u0AFF])|નહિ(?![\u0A80-\u0AFF])|ક્યારેય|કોઈને", re.I)
NEG_EN_BEFORE = re.compile(r"\b(?:do\s*n[o']?t|never|not\s+to|avoid|beware|won'?t|will\s+not|doesn'?t|does\s+not)\b", re.I)


def _warned(sent):
    return bool(WARN_CUE.search(sent))


def _digital_arrest(text):
    for sent in _SENT.split(text):
        m = DIGITAL_ARREST.search(sent)
        if m and not _warned(sent) and not _NEG_ITEM.search(m.group(0)):
            return True
    return False


def _card_ask(text):
    """Request to share ATM PIN / CVV / card number / expiry. Warnings ABOUT not sharing them are not a request."""
    for sent in _SENT.split(text):
        if not CARD_ITEM.search(sent):
            continue
        v_en, v_in = CARD_VERB_EN.search(sent), CARD_VERB_IN.search(sent)
        if not (v_en or v_in) or NEG_IN.search(sent):
            continue
        if v_en and not v_in and NEG_EN_BEFORE.search(sent[:v_en.start()]):
            continue
        if _warned(sent) and re.search(r"\bnever\b|ક્યારેય|कभी", sent, re.I):
            continue
        return True
    return False


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
    # --- authority impersonation / digital arrest / safe-account / card-detail scams ---
    da = _digital_arrest(text)
    if da:
        add(3, "Fake police/CBI/customs/TRAI 'digital arrest' scare (classic scam)")
    auth_threat = bool(AUTHORITY.search(text) and LEGAL_THREAT.search(text) and ADDRESSES_YOU.search(text)) and not WARN_CUE.search(text)
    if auth_threat and not da:
        add(2, "Claims to be police/CBI/customs/court and threatens arrest or a case")
    coerce = bool(COERCE.search(text)) and not WARN_CUE.search(text)
    if coerce:
        add(2, "Pressures you to stay on a (video) call")
    if SECRECY.search(text) and (auth_threat or da or coerce) and not WARN_CUE.search(text):  # "don't tell anyone" alone is normal (surprise party)
        add(2, "Tells you to keep it secret")
    if not WARN_CUE.search(text):
        if SAFE_ACCT.search(text) and re.search(_MOVE, text, re.I):
            add(3, "Asks you to move money to a 'safe'/RBI account")
        elif VERIFY_TRANSFER.search(text):
            add(3, "Asks you to transfer money 'for verification/investigation' (refund promise)")
    if _card_ask(text):
        add(3, "Asks you to share your ATM PIN, CVV or card details (OTP/PIN request)")
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
