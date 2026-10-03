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
