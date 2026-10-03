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
         "epfindia.gov.in", "pay.google.com", "bhimupi.org.in", "wa.me",
         "myvi.in", "bsnl.in", "airtel.com", "vodafoneidea.com", "jiomart.com", "jio.in", "bankofbaroda.in", "pnb.co.in", "canarabank.com",
         "unionbankofindia.co.in", "idfcfirstbank.com", "indusind.com", "yesbank.in", "delhivery.com", "bluedart.com", "dtdc.in", "uber.com"]

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
OTP_ASK = re.compile(r"\b(?:share|send|forward|tell|give|provide|read out|reply|confirm|enter|submit|batao|bhejo)\b|बताएं|बताइए|बताइये|भेजें|बताओ|साझा|शेयर|શેર|મોકલો|જણાવો", re.I)
NEGATION = re.compile(r"\b(?:do not|don'?t|dont|never|not to|do NOT|avoid|beware|mat|nahi|nahin|kabhi)\b|मत|न करें|ન કરો|નહીં|ના કરો|"
                      r"(?<![\u0900-\u097F])न\s+(?:बताएं|बताइए|बताइये|बताओ|दें|भेजें|शेयर|साझा|करना|कीजिए)|साझा\s*न|शेयर\s*न|"
                      r"(?<![\u0A80-\u0AFF])(?:ન|ના)\s*(?:આપો|જણાવો|કહો|મોકલો|કરશો|આપશો)|કોઈને", re.I)
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
WARN_CUE = re.compile(r"\b(?:scams?|beware|aware(?:ness)?|never|fake calls?|ignore such|report such|is\s+a\s+(?:fraud|scam)|(?:scam|fraud|cyber)\s+alert|scam\s+(?:hai|h)|stay\s+alert)\b|"
                      r"सावधान|जागरूक|सतर्क|ठगी\s*(?:से|है)|धोखाधड़ी\s*है|स्कैम\s*है|कभी\s*नहीं|कभी|"
                      r"સાવધ\w*|જાગૃત|સતર્ક|ક્યારેય|છેતરપિંડી\s*છે|ઠગાઈ\s*છે|ધોખાધડી\s*છે|સ્કેમ\s*છે", re.I)

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
    r"do\s*n[o']?t\s+(?:disconnect|cut|hang\s*up|end)\s+(?:the\s+|this\s+)?(?:video\s+)?call|stay\s+(?:on|connected\s+(?:on|to))\s+(?:the\s+|this\s+)?(?:video\s+)?(?:call|line|skype|zoom|google\s*meet|whatsapp)|"
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
        if m and not _NEG_ITEM.search(m.group(0)):
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


# ---- F8: awareness over the whole message, plus task/loan-app/sextortion/UPI-PIN/officer-pay/case-pay scams ----
_ASK_VERB = re.compile(r"\b(?:pay|send|transfer|deposit|click|tap|download|install|remit|bhejo|bhej\w*)\b|भेजें|भेजो|ट्रांसफर|जमा\s*करें|मोકલો|મોકલો|ટ્રાન્સફર|જમા\s*કરો", re.I)
_URGENT_NOW = re.compile(r"\bnow\b|immediately|today|within|तुरंत|अभी|આજે|તરત|હમણાં", re.I)


def real_ask(text):
    """A sentence that really asks for action (pay/send/click + a link, amount, UPI id or phone), not itself a warning."""
    for sent in _SENT.split(text):
        if not sent.strip() or WARN_CUE.search(sent) or NEGATION.search(sent) or not _ASK_VERB.search(sent):
            continue
        ex = extract(sent)
        if ex["urls"] or ex["amounts"] or ex["upi_ids"] or ex["phones"]:
            return True
    return False


def _sent_hit(rx, text, guard=True):
    """rx matches inside a sentence that does not itself negate/warn (e.g. 'never enter your PIN to receive money')."""
    for sent in _SENT.split(text):
        m = rx.search(sent)
        if m and not (guard and (NEG_IN.search(sent) or NEG_EN_BEFORE.search(sent[:m.start() + 1]) or _warned(sent))):
            return True
    return False


UPI_PIN_TRICK = re.compile(
    r"(?:upi\s*)?pin\s+(?:daal\w*|dal\w*|dalo|enter\s+kar\w*|bhar\w*|nakho)\b.{0,50}\b(?:paisa|paise|money|refund|cashback|credit|aayega|ayega|aa\s*jayega|milega|mil\s*jayega)|"
    r"\b(?:paisa|paise|money|refund|cashback)\b.{0,50}\b(?:upi\s*)?pin\s+(?:daal\w*|dal\w*|dalo|enter\s+kar\w*|bhar\w*|nakho)|"
    r"पिन\s*(?:डालें|डालिए|डालिये|डालो|दर्ज\s*करें|एंटर\s*करें).{0,50}(?:पैसे|रुपये|रुपए|रिफंड|कैशबैक|आएंगे|आएगा|मिलेंगे|मिलेगा)|"
    r"(?:पैसे|रुपये|रुपए|रिफंड|कैशबैक).{0,50}पिन\s*(?:डालें|डालिए|डालिये|डालो|दर्ज\s*करें|एंटर\s*करें)|"
    r"(?:પૈસા|રિફંડ|કેશબેક|રૂપિયા).{0,50}પિન\s*(?:નાખો|નાખજો|દાખલ\s*કરો|એન્ટર\s*કરો)|"
    r"પિન\s*(?:નાખો|નાખજો|દાખલ\s*કરો|એન્ટર\s*કરો).{0,50}(?:પૈસા|રિફંડ|કેશબેક|આવશે|મળશે)", re.I)

_PLAT = r"(?:youtube\s+|instagram\s+|google\s+maps\s+|facebook\s+)?"
_UNIT = r"(?:like|video|task|review|rating|click|follow|subscribe|लाइक|वीडियो|टास्क|रिव्यू|રિવ્યૂ|લાઈક|લાઇક|વીડિયો|ટાસ્ક)s?"
JOB_PER = re.compile(
    r"(?:earn\w*|income|paid|pay(?:ment)?|get|milega|milenge|kamao|kamaye|कमाएं|कमाओ|कमाएँ|કમાઓ|કમાવો)\b.{0,50}\b(?:per|each|every|for\s+each|for\s+every|har|prati|हर|प्रति|દરેક|પ્રતિ)\s*" + _PLAT + _UNIT + r"|"
    r"(?:har|every|each|हर|દરેક)\s+" + _PLAT + _UNIT + r"\s*(?:par|pe|पर|के\s*लिए|માટે|પર)?\s*(?:rs\.?|₹|rupay\w*|rupee\w*|रुपये|રૂપિયા)?\s*\d+|"
    r"(?:rs\.?|₹)\s*\d[\d,]*\s*(?:per|/|for\s+each|for\s+every)\s*" + _PLAT + r"(?:like|video|task|review)|"
    r"like\s+(?:and|&|\+)\s+subscribe.{0,40}(?:earn|rs|₹|paid)", re.I)
TELEGRAM_TASK = re.compile(r"(?:telegram|whatsapp)\s+(?:group|channel).{0,60}(?:task|like|video|earn|work|job)|(?:task|earn\w*|part[- ]?time).{0,60}(?:telegram|whatsapp)\s+(?:group|channel)|"
                           r"टेलीग्राम.{0,40}(?:टास्क|ग्रुप)|ટેલિગ્રામ.{0,40}(?:ટાસ્ક|ગ્રુપ)", re.I)
PREPAY = re.compile(r"(?:deposit|invest|prepaid?|pay|recharge|registration|activation|security)\b.{0,50}(?:unlock|withdraw|tasks?\b|earnings?|commission|profit)|unlock\w*.{0,40}(?:earnings?|tasks?|withdraw|commission)|"
                    r"(?:prepaid|prepay)\s+tasks?|(?:पैसे|रुपये|रुपए)\s*जमा.{0,40}(?:टास्क|कमीशन|कमाई)|પૈસા\s*જમા.{0,40}(?:ટાસ્ક|કમિશન|કમાણી)|ડિપોઝિટ.{0,40}(?:કમાણી|કમિશન|ટાસ્ક)", re.I)
JOB_CTX = re.compile(r"\bjob\b|\btasks?\b|\bearn\w*|income|commission|part[- ]?time|work\s+from\s+home|\blikes?\b|youtube|telegram|नौकरी|टास्क|कमाई|कमाएं|નોકરી|ટાસ્ક|કમાણી", re.I)
PART_TIME = re.compile(r"part[- ]?time\s+jobs?|work\s+from\s+home|घर\s*बैठे|पार्ट\s*टाइम|પાર્ટ\s*ટાઇમ|ઘરે\s*બેઠા", re.I)
EARN_W = re.compile(r"\bearn\w*|daily\s+income|per\s+day|/\s*day|कमाएं|कमाई|कमाओ|દરરોજ|કમાણી|કમાઓ", re.I)

_GRP_EN = r"(?:contacts?|contact\s*list|family|friends?|relatives?|parents|wife|husband|whatsapp|facebook|social\s*media|rishtedar\w*|ghar\s*walo\w*)"
SHARE_TO_CONTACTS = re.compile(
    r"(?:send|share|post|upload|circulate|forward|leak|viral|bhej\w*|dikha\w*)\b.{0,70}\b(?:all\s+)?(?:your|ur|tumhare|tumhari|aapke|aapki)\s+" + _GRP_EN + r"|"
    r"(?:your|ur|tumhare|aapke)\s+" + _GRP_EN + r"\s+(?:ko|to)\b.{0,50}(?:send|share|bhej\w*|viral|photo|video|message|call)|"
    r"(?:आपके|तुम्हारे)\s+(?:परिवार|रिश्तेदार\w*|दोस्त\w*|कॉन्टैक्ट\w*|संपर्क\w*|घरवाल\w*).{0,50}(?:भेज|वायरल|शेयर|दिखा)\w*|"
    r"(?:भेज|वायरल|शेयर)\w*.{0,50}(?:आपके|तुम्हारे)\s+(?:परिवार|रिश्तेदार\w*|दोस्त\w*|कॉन्टैक्ट\w*|संपर्क\w*)|"
    r"તમારા\s+(?:પરિવાર|સંબંધી\w*|મિત્ર\w*|કોન્ટેક્ટ\w*|સંપર્ક\w*|ઘરના\w*).{0,50}(?:મોકલ|વાયરલ|શેર|બતાવ)\w*|"
    r"(?:મોકલ|વાયરલ|શેર)\w*.{0,50}તમારા\s+(?:પરિવાર|સંબંધી\w*|મિત્ર\w*|કોન્ટેક્ટ\w*|સંપર્ક\w*)", re.I)
DEFAME = re.compile(r"defam\w*|badnaam\w*|bad\s*name|expose\s+you|humiliat\w*|insult\s+you|बदनाम\w*|બદનામ\w*", re.I)
LOAN_CTX = re.compile(r"\bloans?\b|\bemi\b|repay\w*|recovery|लोन|कर्ज़?|उधार|લોન|ઉધાર|ચૂકવ", re.I)
SEXT_HAVE = re.compile(
    r"(?:i|we)\s+(?:have|got|recorded|captured|saved)\s+(?:your\s+)?(?:nude|naked|private|obscene|intimate|objectionable|screen\s*record\w*|video|videos|photos?|pictures?|pics?|recording|chat)|"
    r"your\s+(?:nude|naked|private|obscene|intimate|objectionable)\s+(?:video|videos|photos?|pictures?|pics?|recording)|"
    r"(?:tumhari|aapki|teri)\s+(?:nude|private|gandi|vulgar|obscene)?\s*(?:video|videos|photo|photos|pics?)\w*\s+(?:mere|hamare|meri)\s+paas|"
    r"(?:तुम्हारी|आपकी|तेरी)\s+(?:न्यूड|नग्न|प्राइवेट|अश्लील)?\s*(?:वीडियो|फोटो|तस्वीर)\w*.{0,30}(?:मेरे|हमारे)\s*पास|"
    r"(?:તમારો|તમારી|તારો|તારી)\s+(?:ન્યૂડ|પ્રાઇવેટ|અશ્લીલ)?\s*(?:વીડિયો|ફોટો|ફોટા)\w*.{0,30}(?:મારી|અમારી)\s*પાસે", re.I)
LEAK_W = re.compile(r"viral|leak|upload|\bpost\b|share|send\s+(?:it|them|this)|वायरल|लीक|शेयर|भेज|વાયરલ|લીક|શેર|મોકલ", re.I)
MONEY_W = re.compile(r"\bpay\b|paise|paisa|money|rs\.?\s*\d|₹|rupees|transfer|पैसे|रुपये|रुपए|भुगतान|पैसा|પૈસા|રૂપિયા|ચૂકવ", re.I)
OFFICER = re.compile(r"\bofficer\b|\binspector\b|\bsir\b.{0,10}\bcbi\b|अधिकारी|इंस्पेक्टर|અધિકારી|ઇન્સ્પેક્ટર", re.I)
VIDEO_PLAT = re.compile(r"skype|zoom|google\s*meet|whatsapp\s+video|video\s+call|वीडियो\s*कॉल|સ્કાઇપ|स्काइप|વીડિયો\s*કૉલ|વિડિયો\s*કૉલ", re.I)
SEND_MONEY = re.compile(r"\b(?:send|transfer|deposit|pay)\b.{0,40}(?:rs\.?|₹|inr)?\s*\d[\d,]{2,}|(?:rs\.?|₹)\s*\d[\d,]{2,}.{0,30}\b(?:send|transfer|deposit|pay)\b|"
                        r"(?:भेजें|ट्रांसफर|जमा).{0,30}\d[\d,]{3,}|\d[\d,]{3,}.{0,30}(?:भेजें|ट्रांसफर|जमा)|(?:મોકલો|ટ્રાન્સફર|જમા).{0,30}\d[\d,]{3,}|\d[\d,]{3,}.{0,30}(?:મોકલો|ટ્રાન્સફર|જમા)", re.I)
CASE_AGAINST_SIM = re.compile(
    r"(?:case|fir|complaint)\b.{0,50}\b(?:against|on|under)\b.{0,25}\b(?:your|you)\b.{0,25}\b(?:sim|mobile|number|aadhaar|aadhar|bank\s*account)|"
    r"\b(?:sim|mobile\s*number|aadhaar)\b.{0,40}\b(?:case|fir)\b.{0,30}(?:registered|filed|lodged)|"
    r"(?:aapke|tumhare)\s+(?:sim|number|aadhaar)\s+(?:ke\s+naam\s+par|par)\s+(?:case|fir)|"
    r"(?:आपके|तुम्हारे)\s*(?:सिम|नंबर|आधार).{0,30}(?:केस|एफआईआर)|(?:सिम|नंबर|आधार).{0,30}(?:पर|के\s*खिलाफ|के\s*नाम\s*पर).{0,20}(?:केस|एफआईआर)|"
    r"(?:તમારા)\s*(?:સિમ|નંબર|આધાર).{0,30}(?:કેસ|ફરિયાદ)|(?:સિમ|નંબર|આધાર).{0,30}(?:સામે|પર|ના\s*નામે).{0,20}(?:કેસ|ફરિયાદ)", re.I)
CLOSE_CASE_PAY = re.compile(
    r"(?:pay|payment|fine|fee|deposit|transfer|send)\b.{0,60}\b(?:close|settle|clear|quash|cancel|withdraw|dismiss)\w*\s+(?:the\s+|this\s+|your\s+)?(?:case|fir|complaint)|"
    r"(?:close|settle|clear|quash|cancel|dismiss)\w*\s+(?:the\s+|this\s+|your\s+)?(?:case|fir)\b.{0,60}\b(?:pay|payment|fine|fee|deposit|transfer|send)|"
    r"case\s+(?:close|band|khatam)\s+kar\w*.{0,40}(?:paise|pay|rs|₹|fine|jama)|(?:paise|pay|rs|₹|fine|jama)\w*.{0,40}case\s+(?:close|band|khatam)|"
    r"(?:केस|एफआईआर)\s*(?:बंद|खत्म|रद्द)\s*(?:करने|कराने)?.{0,50}(?:पैसे|रुपये|रुपए|जुर्माना|भुगतान|जमा)|(?:पैसे|रुपये|रुपए|जुर्माना|भुगतान|जमा).{0,50}(?:केस|एफआईआर)\s*(?:बंद|खत्म|रद्द)|"
    r"(?:કેસ|ફરિયાદ)\s*(?:બંધ|રદ)\s*(?:કરવા|કરાવવા)?.{0,50}(?:પૈસા|રૂપિયા|દંડ|ચૂકવ|જમા)|(?:પૈસા|રૂપિયા|દંડ|ચૂકવ|જમા).{0,50}(?:કેસ|ફરિયાદ)\s*(?:બંધ|રદ)", re.I)


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


_AVOID = re.compile(r"\bavoid\b(?!\s+(?:shar|disclos|giv|tell|reveal))", re.I)  # "share OTP to avoid block" is an ask; "avoid sharing OTP" is a warning
_DELIVERY_OK = re.compile(r"(?:deliver\w*|doorstep).{0,60}\b(?:only|at the time|on delivery|upon delivery|when)\b|\bonly\b.{0,50}(?:deliver\w*|doorstep)|"
                          r"at the time of delivery", re.I)  # genuine e-commerce: "share OTP with the delivery partner ONLY on delivery"
_PERSON = (r"(?:executive|officer|agent|caller|representative|customer\s*(?:care|support|service)|manager|employee|staff|official|"
           r"advisor|banker|person|someone|sir|madam|अधिकारी|एग्ज़ीक्यूटिव|એક્ઝિક્યુટિવ|અધિકારી)")
PERSON_ASK = re.compile(r"\b(?:share|tell|give|send|read\s*out|provide|forward|disclose|reveal)\b.{0,50}\b(?:with|to)\s+(?:our|the|a|an|my|this|that|bank)?\s*(?:\w+\s+){0,2}" + _PERSON, re.I)
OTP_ASK2 = re.compile(r"\bbata\s*(?:do|dijiye|dijiye|dena|de|iye|iyega)\b|\bbataiye\b|\bbatayiye\b|\bbhej\s*(?:do|dijiye|na)\b|\bshare\s+k\w+|\bde\s*do\b|\bdijiye\b|\bbolo\b", re.I)
NEG_HINGLISH = re.compile(r"\bna\s+(?:kar\w*|bata\w*|de\b|do\b|bhej\w*|share)|\bnahi\b|\bnahin\b|\bmat\b|\bnot\s+(?:to\s+)?(?:share|tell|give)", re.I)


def _otp_request(text):
    for sent in _SENT.split(text):
        if not OTP_WORD.search(sent):
            continue
        s = re.sub(r"\bnahi\s*to(?:h)?\b|\bnahin\s*to\b", "", _AVOID.sub("", sent), flags=re.I)  # "nahi to" = "otherwise", not a negation
        if _DELIVERY_OK.search(s) and not ASK_OVER_PHONE.search(s):
            continue
        ask = OTP_ASK.search(s) or OTP_ASK2.search(s)
        if not ask:
            continue
        neg = NEGATION.search(s) or NEG_HINGLISH.search(s)
        if not neg:
            return True
        # a negation does not clear an explicit "give it to a person" ask unless the negation comes first ("never share ... with staff")
        pm = PERSON_ASK.search(s)
        if pm:
            before = s[:pm.start()]
            if not (NEGATION.search(before) or NEG_HINGLISH.search(before) or NEG_EN_BEFORE.search(before)):
                return True
    return False


ASK_OVER_PHONE = re.compile(r"over\s+(?:the\s+)?(?:phone|call)\s*(?!.*\b(?:do not|don'?t|never)\b)|send\s+(?:it\s+)?to\s+\+?\d|whatsapp", re.I)


def analyze(text):
    text = text or ""
    ex = extract(text)
    flags = []  # (weight, label)

    def add(w, label):
        flags.append((w, label))

    aware = bool(WARN_CUE.search(text))
    mute = aware and not real_ask(text)  # awareness anywhere in the message (neighbouring sentences) unless it also makes a real ask

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
    if _otp_request(text) and not mute and not (COLLECT.search(text) and not mute):
        add(3, "Asks you to share/enter OTP, PIN or password")
    collect = bool(COLLECT.search(text)) and _sent_hit(COLLECT, text) and not mute
    if collect or (_sent_hit(UPI_PIN_TRICK, text) and not mute):
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
    da = _digital_arrest(text) and not mute
    if da:
        add(3, "Fake police/CBI/customs/TRAI 'digital arrest' scare (classic scam)")
    auth_threat = bool(AUTHORITY.search(text) and LEGAL_THREAT.search(text) and ADDRESSES_YOU.search(text)) and not mute
    if auth_threat and not da:
        add(2, "Claims to be police/CBI/customs/court and threatens arrest or a case")
    coerce = bool(COERCE.search(text)) and not mute
    if coerce:
        add(2, "Pressures you to stay on a (video) call")
    if SECRECY.search(text) and (auth_threat or da or coerce) and not mute:  # "don't tell anyone" alone is normal (surprise party)
        add(2, "Tells you to keep it secret")
    if not mute:
        if SAFE_ACCT.search(text) and re.search(_MOVE, text, re.I):
            add(3, "Asks you to move money to a 'safe'/RBI account")
        elif VERIFY_TRANSFER.search(text):
            add(3, "Asks you to transfer money 'for verification/investigation' (refund promise)")
    if _card_ask(text):
        add(3, "Asks you to share your ATM PIN, CVV or card details (OTP/PIN request)")
    # --- F8 scam families ---
    if not mute:
        if JOB_PER.search(text) or TELEGRAM_TASK.search(text) or (PREPAY.search(text) and JOB_CTX.search(text)):
            add(3, "Task/job scam: pay-to-earn per like/video/task (fake job)")
        elif PART_TIME.search(text) and EARN_W.search(text):
            add(2, "Task/job scam: pay-to-earn per like/video/task (fake job)")
        shares = bool(SHARE_TO_CONTACTS.search(text))
        sext = bool(SEXT_HAVE.search(text)) and (shares or LEAK_W.search(text)) and MONEY_W.search(text)
        if sext or (shares and re.search(r"\b(?:video|photos?|pics?|pictures?)\b|वीडियो|फोटो|વીડિયો|ફોટો", text, re.I) and MONEY_W.search(text) and not LOAN_CTX.search(text)):
            add(3, "Blackmail threat to leak your private video/photos unless you pay")
        elif LOAN_CTX.search(text) and (shares or DEFAME.search(text)):
            add(3, "Loan-app style threat to shame you / send your photos or contacts")
        if (AUTHORITY.search(text) or OFFICER.search(text)) and VIDEO_PLAT.search(text) and SEND_MONEY.search(text):
            add(3, "Officer on a video call/Skype asks you to send money")
        case_sim, case_pay = bool(CASE_AGAINST_SIM.search(text)), bool(CLOSE_CASE_PAY.search(text))
        if case_pay and (case_sim or LEGAL_THREAT.search(text)):
            add(3, "Says a case is registered against you and asks payment to close it")
        elif case_sim and not da and not auth_threat:
            add(2, "Claims to be police/CBI/customs/court and threatens arrest or a case")
    if REFUND.search(text) and (ex["upi_ids"] or ex["urls"] or ex["phones"]):
        add(1, "Refund/cashback bait with a contact or link")
    if ex["upi_ids"] and re.search(r"\b(?:pay|send|transfer)\b", text, re.I) and ex["amounts"]:
        # awareness wording must not launder a real payment request to a UPI id
        add(3 if (aware and real_ask(text)) else 1, "Asks for payment to a personal UPI ID")

    seen, labels = set(), []
    for w, l in flags:
        if l not in seen:
            seen.add(l)
            labels.append((w, l))
    if labels and ex["urls"] and all(l.startswith(("Urgency / threat words", "Link is not secure")) for _, l in labels) and \
            all(any(_host(u) == d or _host(u).endswith("." + d) for d in LEGIT) for u in ex["urls"]):
        labels = []  # only weak signals, and every link is an official domain (telco/bank expiry reminders): not a flag
    total = sum(w for w, _ in labels)
    strong = any(w >= 3 for w, _ in labels)
    score = min(100, total * 20)
    sev = "red" if (strong or total >= 4) else "amber" if total >= 1 else "green"
    weak_only = bool(labels) and all(l.startswith("Urgency / threat words") or l.startswith("Link is not secure") for _, l in labels)
    return {"score": score, "severity": sev, "flags": [l for _, l in labels], "strong": strong, "weak_only": weak_only, "extracted": ex}


def combine(code_severity, llm_verdict, weak_only=False):
    """Final severity = max(code, llm). Never lower than code severity, EXCEPT: when the code found only weak signals
    (urgency wording / http link) and the AI itself says green, trust the AI (strong flags are never overridden)."""
    a = code_severity if code_severity in SEV else "green"
    b = llm_verdict if llm_verdict in SEV else "green"
    if weak_only and a == "amber" and b == "green":
        return "green"
    return a if SEV[a] >= SEV[b] else b
