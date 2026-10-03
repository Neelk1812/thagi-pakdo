"""Draft a formal complaint for the National Cybercrime Reporting Portal (cybercrime.gov.in) from a /api/check result.
AI draft (llm.draft_text) with a deterministic offline template as fallback. Never invents facts: anything the
user did not supply stays a [placeholder] and is listed in missing_fields. Personal details are never logged/cached."""
import hashlib, json, re

import llm

PORTAL_URL, HELPLINE = "https://cybercrime.gov.in", "1930"
LANGS = ("gu", "hi", "en")
FIELDS = ("name", "phone", "date_time", "amount_lost", "payment_method", "transaction_id", "what_happened")
MAX_FIELD = 2000

PH = {  # placeholders per field
    "en": {"name": "[Your name]", "phone": "[Your phone number]", "date_time": "[Date and time of incident]",
           "amount_lost": "[Amount lost, if any]", "payment_method": "[Payment method, e.g. UPI / card / bank transfer]",
           "transaction_id": "[Transaction ID / UTR, if any]", "what_happened": "[Describe what happened in your words]"},
    "hi": {"name": "[आपका नाम]", "phone": "[आपका फ़ोन नंबर]", "date_time": "[घटना की तारीख और समय]",
           "amount_lost": "[गँवाई गई रकम, यदि कोई हो]", "payment_method": "[भुगतान का तरीका, जैसे UPI / कार्ड / बैंक ट्रांसफर]",
           "transaction_id": "[ट्रांज़ैक्शन ID / UTR, यदि हो]", "what_happened": "[अपने शब्दों में बताएँ कि क्या हुआ]"},
    "gu": {"name": "[તમારું નામ]", "phone": "[તમારો ફોન નંબર]", "date_time": "[ઘટનાની તારીખ અને સમય]",
           "amount_lost": "[ગુમાવેલી રકમ, જો કોઈ હોય]", "payment_method": "[ચુકવણીની રીત, જેમ કે UPI / કાર્ડ / બેંક ટ્રાન્સફર]",
           "transaction_id": "[ટ્રાન્ઝેક્શન ID / UTR, જો હોય]", "what_happened": "[તમારા શબ્દોમાં જણાવો કે શું થયું]"},
}
T = {
    "en": dict(
        subject="Complaint regarding suspected online fraud ({kind})", kind_default="online scam message",
        to="To,\nThe Officer-in-Charge,\nNational Cybercrime Reporting Portal ({portal})",
        sal="Respectfully,", intro="I, {name} (phone: {phone}), wish to report a suspected cyber fraud that took place on {date_time}.",
        h_what="What happened", h_type="Type of fraud", h_sus="Suspicious details", h_flags="Warning signs noticed",
        h_loss="Loss and payment details", h_req="Request", urls="Link(s)", phones="Phone number(s)", upis="UPI ID(s)", amts="Amount(s) mentioned",
        none="none found", loss_amt="Amount lost", loss_pm="Payment method", loss_tx="Transaction ID",
        req=["Please register this complaint and investigate.", "Please block the above phone number(s), link(s) and UPI ID(s).",
             "Please freeze the beneficiary bank account(s) / UPI handle(s) to prevent further loss and help recover any amount lost."],
        close="I request urgent action. I have also noted the national cybercrime helpline {helpline}.", thanks="Thank you.",
        yours="Yours faithfully,", analysis="An automated check of the message/screenshot rated it \"{verdict}\".",
        verdict={"red": "likely scam", "amber": "suspicious", "green": "looks safe"}),
    "hi": dict(
        subject="संदिग्ध ऑनलाइन ठगी की शिकायत ({kind})", kind_default="ऑनलाइन ठगी संदेश",
        to="सेवा में,\nप्रभारी अधिकारी,\nराष्ट्रीय साइबर अपराध रिपोर्टिंग पोर्टल ({portal})",
        sal="महोदय/महोदया,", intro="मैं, {name} (फ़ोन: {phone}), {date_time} को हुई एक संदिग्ध साइबर ठगी की शिकायत दर्ज कराना चाहता/चाहती हूँ।",
        h_what="क्या हुआ", h_type="ठगी का प्रकार", h_sus="संदिग्ध जानकारी", h_flags="देखे गए चेतावनी संकेत",
        h_loss="नुकसान और भुगतान की जानकारी", h_req="अनुरोध", urls="लिंक", phones="फ़ोन नंबर", upis="UPI ID", amts="बताई गई रकम",
        none="कोई नहीं मिला", loss_amt="गँवाई गई रकम", loss_pm="भुगतान का तरीका", loss_tx="ट्रांज़ैक्शन ID",
        req=["कृपया यह शिकायत दर्ज करें और जाँच करें।", "कृपया ऊपर दिए गए फ़ोन नंबर, लिंक और UPI ID को ब्लॉक करें।",
             "कृपया लाभार्थी बैंक खाते / UPI खाते को फ़्रीज़ करें ताकि और नुकसान न हो और गँवाई गई रकम वापस मिल सके।"],
        close="मेरा अनुरोध है कि तुरंत कार्रवाई की जाए। मैंने राष्ट्रीय साइबर अपराध हेल्पलाइन {helpline} का भी ध्यान रखा है।", thanks="धन्यवाद।",
        yours="भवदीय,", analysis="संदेश/स्क्रीनशॉट की स्वचालित जाँच में इसे \"{verdict}\" आँका गया।",
        verdict={"red": "संभावित ठगी", "amber": "संदिग्ध", "green": "सुरक्षित लगता है"}),
    "gu": dict(
        subject="શંકાસ્પદ ઓનલાઇન છેતરપિંડી અંગે ફરિયાદ ({kind})", kind_default="ઓનલાઇન છેતરપિંડીનો સંદેશ",
        to="પ્રતિ,\nપ્રભારી અધિકારીશ્રી,\nનેશનલ સાયબર ક્રાઇમ રિપોર્ટિંગ પોર્ટલ ({portal})",
        sal="માનનીય સાહેબ/મેડમ,", intro="હું, {name} (ફોન: {phone}), {date_time} ના રોજ બનેલી એક શંકાસ્પદ સાયબર છેતરપિંડીની ફરિયાદ નોંધાવવા માગું છું.",
        h_what="શું બન્યું", h_type="છેતરપિંડીનો પ્રકાર", h_sus="શંકાસ્પદ વિગતો", h_flags="જોવા મળેલા ચેતવણીના સંકેતો",
        h_loss="નુકસાન અને ચુકવણીની વિગતો", h_req="વિનંતી", urls="લિંક", phones="ફોન નંબર", upis="UPI ID", amts="જણાવેલી રકમ",
        none="કોઈ મળ્યું નથી", loss_amt="ગુમાવેલી રકમ", loss_pm="ચુકવણીની રીત", loss_tx="ટ્રાન્ઝેક્શન ID",
        req=["કૃપા કરીને આ ફરિયાદ નોંધો અને તપાસ કરો.", "કૃપા કરીને ઉપરના ફોન નંબર, લિંક અને UPI ID બ્લૉક કરો.",
             "કૃપા કરીને લાભાર્થી બેંક ખાતું / UPI ખાતું ફ્રીઝ કરો, જેથી વધુ નુકસાન ન થાય અને ગુમાવેલી રકમ પાછી મળી શકે."],
        close="મારી વિનંતી છે કે તાત્કાલિક કાર્યવાહી કરવામાં આવે. મેં રાષ્ટ્રીય સાયબર ક્રાઇમ હેલ્પલાઇન {helpline} પણ નોંધી છે.", thanks="આભાર.",
        yours="આપનો વિશ્વાસુ,", analysis="સંદેશ/સ્ક્રીનશૉટની સ્વચાલિત તપાસમાં તેને \"{verdict}\" ગણવામાં આવ્યો.",
        verdict={"red": "સંભવિત છેતરપિંડી", "amber": "શંકાસ્પદ", "green": "સુરક્ષિત લાગે છે"}),
}
LANG_NAME = {"gu": "Gujarati (ગુજરાતી)", "hi": "Hindi (हिन्दी)", "en": "English"}


def clean_details(details):
    out = {}
    for k in FIELDS:
        v = (details or {}).get(k)
        v = " ".join(str(v).split())[:MAX_FIELD] if v is not None else ""
        if v:
            out[k] = v
    return out


def _facts(result):
    ex = result.get("extracted") or {}
    g = lambda k: [str(x) for x in (ex.get(k) or []) if str(x).strip()]
    return {"urls": g("urls"), "phones": g("phones"), "upi_ids": g("upi_ids"), "amounts": g("amounts"),
            "flags": [str(x) for x in (result.get("red_flags_found") or []) if str(x).strip()],
            "reasons": [str(x) for x in (result.get("reasons") or []) if str(x).strip()],
            "scam_type": str(result.get("scam_type") or "").strip(), "verdict": str(result.get("verdict") or "")}


def cache_key(result, lang):
    """Stable over the fields that matter (not 'source'/timing), so the prewarmed key == the live key."""
    f = _facts(result)
    return hashlib.sha256(json.dumps([f, lang], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def missing_fields(details):
    d = clean_details(details)
    return [k for k in FIELDS if k not in d]


def template(result, lang, details=None):
    """Deterministic, offline. Returns {subject, body}."""
    t, f, d = T[lang], _facts(result), clean_details(details)
    val = lambda k: d.get(k) or PH[lang][k]
    kind = f["scam_type"] or t["kind_default"]
    lines = [t["to"].format(portal=PORTAL_URL), "", t["sal"], "", t["intro"].format(name=val("name"), phone=val("phone"), date_time=val("date_time")), ""]
    lines += [f"{t['h_what']}:", val("what_happened")]
    if f["verdict"] in t["verdict"]:
        lines.append(t["analysis"].format(verdict=t["verdict"][f["verdict"]]))
    lines += ["", f"{t['h_type']}: {kind}", "", f"{t['h_sus']}:"]
    for label, key in (("urls", "urls"), ("phones", "phones"), ("upis", "upi_ids"), ("amts", "amounts")):
        lines.append(f"- {t[label]}: {', '.join(f[key]) if f[key] else t['none']}")
    pts = f["flags"] + [r for r in f["reasons"] if r not in f["flags"]]
    if pts:
        lines += ["", f"{t['h_flags']}:"] + [f"- {p}" for p in pts[:8]]
    lines += ["", f"{t['h_loss']}:", f"- {t['loss_amt']}: {val('amount_lost')}", f"- {t['loss_pm']}: {val('payment_method')}",
              f"- {t['loss_tx']}: {val('transaction_id')}", "", f"{t['h_req']}:"]
    lines += [f"{i}. {r}" for i, r in enumerate(t["req"], 1)]
    lines += ["", t["close"].format(helpline=HELPLINE), t["thanks"], "", t["yours"], val("name"), val("phone")]
    return {"subject": t["subject"].format(kind=kind), "body": "\n".join(lines)}


def _prompt(result, lang, details):
    f, d = _facts(result), clean_details(details)
    given = {k: d[k] for k in FIELDS if k in d}
    ph = {k: PH[lang][k] for k in FIELDS if k not in d}
    facts = json.dumps({k: f[k] for k in ("verdict", "scam_type", "reasons", "flags", "urls", "phones", "upi_ids", "amounts")}, ensure_ascii=False)
    return f"""You draft formal complaints for the National Cybercrime Reporting Portal of India ({PORTAL_URL}, helpline {HELPLINE}).
Write the complaint in {LANG_NAME[lang]}. Reply with ONLY one JSON object: {{"subject":"...","body":"..."}} (body is plain text with line breaks as \\n, no markdown).
Body must include: addressee, short incident summary, scam type, ALL suspicious URLs / phone numbers / UPI IDs / amounts listed below, the red flags, loss details (if any), and a request to block the number(s), URL(s) and UPI ID(s) and to freeze the beneficiary bank account(s), and a polite closing.
STRICT RULES: values under USER DETAILS are known - write them as plain text, WITHOUT square brackets. Only PLACEHOLDERS go in square brackets. Use ONLY the facts below. NEVER invent names, dates, amounts, bank names, transaction IDs or events. For every item in PLACEHOLDERS write that placeholder VALUE (the bracketed text, exactly as given, in the complaint language - never the English key name) where the value belongs.
ANALYSIS FACTS: {facts}
USER DETAILS (verbatim, may be empty): {json.dumps(given, ensure_ascii=False)}
PLACEHOLDERS (unknown fields): {json.dumps(ph, ensure_ascii=False)}"""


def _unbracket(text, details):
    """Filled values must read plain: drop any [..]/(..)-style brackets the model put around a value the user supplied."""
    for v in sorted((details or {}).values(), key=len, reverse=True):
        text = re.sub(r"[\[【]\s*" + re.escape(v) + r"\s*[\]】]", lambda m: v, text, flags=re.I)
    return text


def _validator(result, lang, details=None):
    f = _facts(result)
    details = clean_details(details)

    def v(raw):
        obj = llm._first_object(llm._strip_noise(raw or "")) if isinstance(raw, str) else None
        if not obj:
            raise ValueError("no JSON")
        d = json.loads(obj)
        subj, body = str(d.get("subject") or "").strip(), str(d.get("body") or "").strip()
        if len(body) < 80 or not subj:
            raise ValueError("incomplete draft")
        pat = re.compile(r"[\[\{<]\s*(" + "|".join(FIELDS) + r")\s*[\]\}>]", re.I)  # model echoed a key instead of the localized placeholder
        body = pat.sub(lambda m: PH[lang][m.group(1).lower()], body)
        subj = pat.sub(lambda m: PH[lang][m.group(1).lower()], subj)
        body, subj = _unbracket(body, details), _unbracket(subj, details)
        missing = [x for x in f["urls"] + f["phones"] + f["upi_ids"] if x not in body]
        if missing:  # never drop a suspicious identifier the user may need the police to block
            body += "\n\n" + T[lang]["h_sus"] + ":\n" + "\n".join("- " + x for x in missing)
        return {"subject": subj[:200], "body": body}
    return v


def build(result, lang, details=None, api_key=None):
    """Returns the final response dict. source = gemini|local|template."""
    d = clean_details(details)
    try:
        draft, source = llm.draft_text(_prompt(result, lang, d), _validator(result, lang, d), **({"api_key": api_key} if api_key is not None else {}))
    except llm.LLMUnavailable:
        draft, source = template(result, lang, d), "template"
    return {**draft, "portal_url": PORTAL_URL, "helpline": HELPLINE, "missing_fields": missing_fields(d), "source": source}
