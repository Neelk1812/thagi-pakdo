import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from checks import analyze, combine

KYC = "SBI Alert: Your KYC is pending. Account will be blocked today. Update immediately: http://bit.ly/sbi-kyc9 "
UPI = "Refund of Rs. 4,999 initiated. Approve the collect request and enter your UPI PIN to receive money. Pay to refund.help@okaxis"
COURIER = "India Post: Your parcel is on hold. Pay customs fee of ₹49 at https://indiapost-redeliver.top/x to reschedule delivery. Call 9876543210"
LOTTERY = "Congratulations! You have won Rs 25,00,000 in KBC lucky draw. Send processing fee to claim prize. WhatsApp +91 98765 43210"
SAFE = "HDFC Bank: OTP 482913 for txn of Rs 1,200.00 at AMAZON. Valid 10 mins. Do not share OTP with anyone. Bank never asks for OTP."


def test_kyc_red():
    r = analyze(KYC)
    assert r["severity"] == "red" and r["score"] >= 60
    assert any("shortener" in f for f in r["flags"]) and r["extracted"]["urls"]


def test_upi_collect_red():
    r = analyze(UPI)
    assert r["severity"] == "red" and "refund.help@okaxis" in r["extracted"]["upi_ids"]
    assert "Rs. 4,999" in r["extracted"]["amounts"]


def test_courier_red():
    r = analyze(COURIER)
    assert r["severity"] == "red" and "9876543210" in r["extracted"]["phones"]
    assert any(".top" in f for f in r["flags"])


def test_lottery_red():
    r = analyze(LOTTERY)
    assert r["severity"] == "red" and any("prize" in f.lower() for f in r["flags"])
    assert r["extracted"]["phones"]


def test_safe_green():
    r = analyze(SAFE)
    assert r["severity"] == "green" and r["flags"] == [], r["flags"]


def test_otp_request_vs_warning():
    assert analyze("Please share your OTP with our agent to verify")["severity"] == "red"
    assert analyze("Do not share OTP with anyone.")["severity"] == "green"
    assert analyze("आपका OTP किसी से साझा न करें")["severity"] == "green"


def test_lookalike_and_punycode():
    assert analyze("Login https://hdfc-secure.com/login")["severity"] == "red"
    assert analyze("Login https://sb1-kyc.in/")["severity"] == "red"
    assert analyze("Visit https://xn--sbi-kyc-9ya.com")["severity"] == "red"
    assert analyze("Visit https://www.hdfcbank.com/offers")["severity"] == "green"


def test_http_only_amber():
    assert analyze("See http://example.com/menu")["severity"] == "amber"


def test_gujarati_hindi_kyc():
    assert analyze("તાત્કાલિક KYC અપડેટ કરો http://bit.ly/abc")["severity"] == "red"


def test_email_not_upi():
    assert analyze("mail me at john@gmail.com")["extracted"]["upi_ids"] == []


def test_empty():
    assert analyze("")["severity"] == "green"


def test_combine():
    assert combine("green", "amber") == "amber"
    assert combine("red", "green") == "red"
    assert combine("amber", "red") == "red"
    assert combine("red", None) == "red"
    assert combine("green", "bogus") == "green"


# ---------------- authority impersonation / digital arrest / safe account / card details ----------------
import pytest


def sev(t):
    return analyze(t)["severity"]


DIGITAL_ARREST_RED = [
    # en
    "This is CBI. A parcel in your name contains drugs. You are under digital arrest. Join the video call now.",
    "Your Aadhaar is linked to a money laundering case. An arrest warrant is issued.",
    "TRAI notice: your mobile number will be disconnected in 2 hours. Press 9 to speak to an officer.",
    "Customs found illegal items in your package. Call the narcotics bureau officer immediately.",
    "Your Aadhaar linked to illegal SIM cards. Cyber crime branch will arrest you.",
    # Hinglish
    "Main CBI officer bol raha hu. Aapke naam par ek parcel mila hai jisme drugs hain. Digital arrest ho sakta hai.",
    "TRAI ki taraf se: aapka number band ho jayega. Abhi officer se baat karein.",
    # hi
    "आपके नाम के पार्सल में ड्रग्स मिले हैं। आप डिजिटल अरेस्ट में हैं, वीडियो कॉल पर बने रहें।",
    "आपके आधार से जुड़े मनी लॉन्ड्रिंग केस में गिरफ्तारी वारंट जारी हुआ है।",
    "ट्राई की ओर से सूचना: आपका नंबर 2 घंटे में बंद कर दिया जाएगा।",
    # gu
    "તમારા નામના પાર્સલમાં ડ્રગ્સ મળ્યા છે. તમે ડિજિટલ અરેસ્ટ હેઠળ છો.",
    "તમારા આધારથી જોડાયેલા મની લોન્ડરિંગ કેસમાં ધરપકડ વોરંટ નીકળ્યું છે.",
    "ટ્રાઈ તરફથી: તમારો નંબર 2 કલાકમાં બંધ કરવામાં આવશે.",
]


@pytest.mark.parametrize("t", DIGITAL_ARREST_RED)
def test_digital_arrest_red(t):
    r = analyze(t)
    assert r["severity"] == "red", r["flags"]
    assert r["strong"]


@pytest.mark.parametrize("t", [
    "Officer from police cyber crime branch here. A case is registered against you. Do not disconnect the call, stay on video call.",
    "Aap par FIR hui hai. Call mat kaatiye, WhatsApp video call par rahiye. Police officer baat karenge.",
    "आपके खिलाफ पुलिस केस दर्ज है। कॉल मत काटिए, वीडियो कॉल पर बने रहें।",
    "તમારી વિરુદ્ધ પોલીસ કેસ નોંધાયો છે. કૉલ કટ ન કરો, વિડિયો કૉલ પર રહો.",
])
def test_authority_plus_call_coercion_red(t):
    assert sev(t) == "red"


def test_authority_threat_alone_is_amber_and_secrecy_escalates():
    assert sev("Police officer here. A case is registered against you.") == "amber"
    assert sev("Police officer here. A case is registered against you. Don't tell anyone.") == "red"
    assert sev("Police aapke khilaf case hai. Kisi ko mat batana.") == "red"
    assert sev("पुलिस आपके खिलाफ केस दर्ज कर चुकी है। किसी को न बताएं।") == "red"


@pytest.mark.parametrize("t", [
    "Transfer Rs 50,000 to the RBI safe account for verification. It is refundable after verification.",
    "Pay the amount to verify your identity; the money will be refunded after verification.",
    "Apne paise RBI ke account me transfer karo, verification ke baad wapas mil jayenge.",
    "जांच के लिए अपने पैसे सुरक्षित खाते में ट्रांसफर करें। सत्यापन के बाद वापस मिल जाएंगे।",
    "તપાસ માટે તમારા પૈસા સુરક્ષિત ખાતામાં ટ્રાન્સફર કરો. ચકાસણી પછી પરત મળશે.",
    "Send money for investigation to this account, it will be returned after the investigation.",
])
def test_safe_account_transfer_red(t):
    r = analyze(t)
    assert r["severity"] == "red", r["flags"]


@pytest.mark.parametrize("t", [
    "Please share your ATM PIN and CVV to verify your account.",
    "Send your card number, expiry date and CVV to complete the refund.",
    "Sir apna ATM PIN batao, card block ho gaya hai.",
    "Card number aur CVV bhejo warna account band.",
    "कृपया अपना एटीएम पिन बताएं ताकि कार्ड चालू रहे।",
    "अपना कार्ड नंबर और सीवीवी भेजें।",
    "તમારો એટીએમ પિન જણાવો, નહીંતર કાર્ડ બંધ થશે.",
    "તમારો કાર્ડ નંબર અને સીવીવી મોકલો.",
])
def test_card_detail_requests_red(t):
    r = analyze(t)
    assert r["severity"] == "red" and any("card details" in f for f in r["flags"])


@pytest.mark.parametrize("t", [
    "HDFC Bank Info: Never share your PIN, CVV or card details with anyone. Bank staff will never ask for them.",
    "Dear customer, do not share your ATM PIN or CVV with anyone, including bank staff.",
    "Our staff will never ask you to share your card number or CVV.",
    "प्रिय ग्राहक, अपना एटीएम पिन या सीवीवी किसी को न बताएं। बैंक कभी नहीं मांगता।",
    "પ્રિય ગ્રાહક, તમારો એટીએમ પિન કે સીવીવી કોઈને શેર ન કરો. બેંક ક્યારેય માંગતી નથી.",
    "Dear customer, apna ATM PIN ya CVV kisi ko share mat karein. Bank kabhi nahi maangta.",
    "Your OTP is 482913. Do not share with anyone.",
])
def test_warnings_about_not_sharing_stay_green(t):
    assert sev(t) == "green", analyze(t)["flags"]


@pytest.mark.parametrize("t", [
    "HDFC Bank: Your a/c XX1234 is credited with Rs 25,000 on 03-Oct. View statement at https://www.hdfcbank.com/statement. Never share OTP/PIN.",
    "Traffic police e-challan paid, thanks",
    "I called the police about the noise, they came and left.",
    "Police arrested two men in a theft case near the market, news says.",
    "Beware: TRAI never calls to say your number will be disconnected. Digital arrest is a scam, ignore such calls.",
    "Reminder: your court hearing for the property matter is on Monday 10 am. Please bring documents.",
    "Don't tell anyone, it's a surprise party for Riya on Saturday!",
    "Your parcel contains books and will be delivered tomorrow by 6 pm.",
    "Your Swiggy order #4521 is out for delivery. Rs 349 paid via UPI.",
    "😀😀🎉🎉🔥🔥💰💰",
])
def test_benign_stays_green(t):
    assert sev(t) == "green", analyze(t)["flags"]
