import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
import app as appmod, llm

c = TestClient(appmod.app)
KYC = "Your KYC is pending, account blocked today. Update: http://bit.ly/x1"


def _down(*a, **k):
    raise llm.LLMUnavailable("x")


def test_code_only(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "check", _down)
    r = c.post("/api/check", data={"text": KYC, "lang": "gu"}).json()
    assert r["verdict"] == "red" and r["ai_unavailable"] and r["source"] == "code" and r["code_flags"]


def test_ai_green_overridden_and_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    ai = {"verdict": "green", "scam_type": "", "reasons": [], "red_flags_found": [], "advice": [],
          "extracted": {"urls": [], "phones": ["9876543210"], "upi_ids": [], "amounts": []}}
    monkeypatch.setattr(llm, "check", lambda *a, **k: (ai, "gemini"))
    r = c.post("/api/check", data={"text": KYC}).json()
    assert r["verdict"] == "red" and r["source"] == "gemini" and "9876543210" in r["extracted"]["phones"]
    monkeypatch.setattr(llm, "check", _down)
    r2 = c.post("/api/check", data={"text": KYC}).json()
    assert r2["source"] == "cache" and r2["verdict"] == "red"


def test_validation():
    assert c.post("/api/check", data={"lang": "en"}).status_code == 400
    big = ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024), "image/png")
    r = c.post("/api/check", files={"image": big})
    assert r.status_code == 413 and r.json()["error"] == "too_large" and r.json()["message"]
    assert c.get("/api/health").json()["ok"]


def test_samples_static():
    r = c.get("/samples/kyc_sms.png")
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    assert c.get("/samples/nope.png").status_code == 404
    assert c.get("/api/health").status_code == 200  # web/ catch-all + api still fine
    assert c.get("/").status_code in (200, 404)


def _png(n):
    import io
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (n, n), (n, 0, 0)).save(b, "PNG"); return b.getvalue()


def test_image_plus_text_cache_key(monkeypatch, tmp_path):
    import hashlib
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    calls = []
    ai = {"verdict": "red", "scam_type": "x", "reasons": ["r"], "red_flags_found": [], "advice": ["a"],
          "extracted": {"urls": [], "phones": [], "upi_ids": [], "amounts": []}}

    def fake(text, image, mime, lang):
        calls.append((text, image, lang))
        return ai, "gemini"
    monkeypatch.setattr(llm, "check", fake)
    png = _png(2)
    f = lambda: {"image": ("a.png", png, "image/png")}
    d = lambda lang: {"text": KYC, "lang": lang}
    r1 = c.post("/api/check", files=f(), data=d("en")).json()
    assert r1["source"] == "gemini" and calls[0][:2] == (KYC, png)  # both image and text reach the LLM
    r2 = c.post("/api/check", files=f(), data=d("en")).json()
    assert r2["source"] == "cache" and len(calls) == 1
    r3 = c.post("/api/check", files=f(), data=d("gu")).json()
    assert r3["source"] == "gemini" and len(calls) == 2  # different lang misses
    key = hashlib.sha256(png + b"\0" + KYC.encode() + b"\0" + b"en").hexdigest()
    assert (tmp_path / f"{key}.json").exists()
    c.post("/api/check", files={"image": ("a.png", _png(3), "image/png")}, data=d("en"))
    assert len(calls) == 3  # different image bytes misses


def test_load_dotenv_does_not_override(monkeypatch, tmp_path):
    f = tmp_path / ".env"
    f.write_text('# c\nFOO_A=1\nexport FOO_B="two words"\nFOO_C=x # note\nFOO_D=keep_me_not\nbad line\n')
    monkeypatch.delenv("FOO_A", raising=False); monkeypatch.delenv("FOO_B", raising=False)
    monkeypatch.delenv("FOO_C", raising=False); monkeypatch.setenv("FOO_D", "orig")
    appmod.load_dotenv(f)
    import os
    assert (os.environ["FOO_A"], os.environ["FOO_B"], os.environ["FOO_C"], os.environ["FOO_D"]) == ("1", "two words", "x", "orig")
    for k in ("FOO_A", "FOO_B", "FOO_C"): os.environ.pop(k, None)


AI_GREEN = {"verdict": "green", "scam_type": "Genuine bank message", "reasons": ["ok"], "red_flags_found": [], "advice": ["a"],
            "extracted": {"urls": [], "phones": [], "upi_ids": [], "amounts": []}}


def test_scam_type_empty_for_green_and_none(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "check", lambda *a, **k: (dict(AI_GREEN), "gemini"))
    r = c.post("/api/check", data={"text": "Your OTP is 123456. Do not share it.", "lang": "en"}).json()
    assert r["verdict"] == "green" and r["scam_type"] == ""
    # AI down + code found nothing -> fail-open AMBER (not green); scam_type is the localized "suspicious" label
    monkeypatch.setattr(llm, "check", _down)
    r = c.post("/api/check", data={"text": "Hello, lunch at 1?", "lang": "hi"}).json()
    assert r["verdict"] == "amber" and r["scam_type"] == appmod.TYPE["amber"]["hi"]
    for junk in ("none", "None", "N/A", " "):
        monkeypatch.setattr(llm, "check", lambda *a, _j=junk, **k: ({**AI_GREEN, "verdict": "red", "scam_type": _j}, "gemini"))
        r = c.post("/api/check", data={"text": "x " + junk, "lang": "en"}).json()
        assert r["scam_type"] == ""
    monkeypatch.setattr(llm, "check", lambda *a, **k: ({**AI_GREEN, "verdict": "red", "scam_type": "Lottery scam"}, "gemini"))
    assert c.post("/api/check", data={"text": "y", "lang": "en"}).json()["scam_type"] == "Lottery scam"


def test_old_cached_green_none_is_normalized(monkeypatch, tmp_path):
    import json
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "check", _down)
    appmod._cache_path(b"", "hello there", "en").write_text(json.dumps({**AI_GREEN, "scam_type": "none", "lang": "en"}))
    r = c.post("/api/check", data={"text": "hello there"}).json()
    assert r["source"] == "cache" and r["scam_type"] == ""


def test_cache_key_whitespace_insensitive_and_sample_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    calls = []
    def fake(*a):
        calls.append(a); return dict(AI_GREEN, verdict="red", scam_type="s"), "gemini"
    monkeypatch.setattr(llm, "check", fake)
    c.post("/api/check", data={"text": "line one\nline two  ", "lang": "en"})
    r = c.post("/api/check", data={"text": "  line one\r\nline   two", "lang": "en"}).json()  # browser CRLF
    assert r["source"] == "cache" and len(calls) == 1
    # sample png sent image-only (or with edited text) resolves to samples/<n>.txt key
    png = (appmod.SAMPLES / "kyc_sms.png").read_bytes(); txt = (appmod.SAMPLES / "kyc_sms.txt").read_text(encoding="utf-8")
    c.post("/api/check", files={"image": ("k.png", png, "image/png")}, data={"text": txt, "lang": "en"})
    n = len(calls)
    for t in ("", "something else"):
        r = c.post("/api/check", files={"image": ("k.png", png, "image/png")}, data={"text": t, "lang": "en"}).json()
        assert r["source"] == "cache" and len(calls) == n


def test_bad_uploads_400(monkeypatch):
    monkeypatch.setattr(llm, "check", _down)
    assert c.post("/api/check", data={"text": "  \n ", "lang": "en"}).status_code == 400
    assert c.post("/api/check").status_code == 400
    assert c.post("/api/check", files={"image": ("a.png", b"hello text", "image/png")}).status_code == 400
    assert c.post("/api/check", files={"image": ("a.png", _noisy()[:300], "image/png")}).status_code == 400  # truncated


def test_endpoint_is_threadpool_sync():
    import inspect
    assert not inspect.iscoroutinefunction(appmod.check)


def _noisy():
    import io, os
    from PIL import Image
    b = io.BytesIO(); Image.frombytes("RGB", (60, 60), os.urandom(60 * 60 * 3)).save(b, "PNG"); return b.getvalue()


def test_cache_write_failure_is_graceful(monkeypatch, tmp_path, caplog):
    """Read-only / unwritable cache dir (e.g. HF Space container): result is still served, warning logged."""
    ro = tmp_path / "ro"; ro.write_text("i am a file, so mkdir/write raises OSError")
    monkeypatch.setattr(appmod, "CACHE", ro)
    monkeypatch.setattr(llm, "check", lambda *a, **k: (dict(AI_GREEN, verdict="red", scam_type="s"), "gemini"))
    r = c.post("/api/check", data={"text": "fresh text for ro cache", "lang": "en"})
    assert r.status_code == 200 and r.json()["source"] == "gemini"
    monkeypatch.setattr(llm, "draft_text", lambda p, v, **k: (v('{"subject":"s","body":"' + "b" * 100 + '"}'), "gemini"))
    r = c.post("/api/complaint", json={"result": {"verdict": "red", "scam_type": "x"}, "lang": "en"})
    assert r.status_code == 200 and r.json()["source"] == "gemini"
    assert "cache write skipped" in caplog.text


def test_starts_without_env_file_and_key_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyFROMENV0123456789abcdefghijk")
    appmod.load_dotenv(tmp_path / "does-not-exist.env")  # missing .env is fine
    assert os.environ["GEMINI_API_KEY"].endswith("ghijk")
    assert c.get("/api/health").json()["gemini_key"] is True


NEW_FLAG_MESSAGES = {  # representative message per new checks.py flag
    "digital_arrest": "This is CBI. A parcel in your name contains drugs. You are under digital arrest.",
    "impersonation": "Police officer here. A case is registered against you.",
    "coerce": "Police officer here. A case is registered against you. Do not disconnect the call, stay on video call.",
    "secret": "Police officer here. A case is registered against you. Don't tell anyone.",
    "safe_acct": "Transfer Rs 50,000 to the RBI safe account immediately.",
    "verify_tx": "Send money for investigation to this account, it will be returned after the investigation.",
    "card": "Please share your ATM PIN and CVV to verify your account.",
    "job_task": "Earn Rs 50 per YouTube like. Join our Telegram group for daily tasks. Pay Rs 1000 deposit to unlock your earnings.",
    "loan_threat": "Repay your loan immediately or we will send your photos and contacts to your family and defame you.",
    "sextortion": "I have your private video. Pay Rs 20000 or I will send it to all your contacts.",
    "officer_pay": "Officer Sharma here. Stay on Skype and send Rs 40000 to this account.",
    "case_pay": "A case is registered against your SIM. Pay Rs 5000 to close the case, else warrant and arrest.",
}


def test_new_flags_have_localized_reasons_code_only(monkeypatch):
    monkeypatch.setattr(llm, "check", _down)
    for key, msg in NEW_FLAG_MESSAGES.items():
        flag_reasons = {}
        for lang in ("en", "hi", "gu"):
            r = c.post("/api/check", data={"text": msg, "lang": lang}).json()
            assert r["ai_unavailable"] and r["verdict"] == ("amber" if key == "impersonation" else "red"), (key, lang, r["verdict"])
            assert r["reasons"] and all(x.strip() for x in r["reasons"]), (key, lang)
            assert appmod.R[key][lang] in r["reasons"], (key, lang)
            flag_reasons[lang] = r["reasons"]
        assert flag_reasons["hi"] != flag_reasons["en"] and flag_reasons["gu"] != flag_reasons["en"]


def test_every_keys_category_has_all_languages_and_old_flags_unchanged():
    for cat, d in appmod.R.items():
        assert set(d) == {"en", "hi", "gu"} and all(d.values()), cat
    assert all(cat in appmod.R for _, cat in appmod.KEYS)
    # old flags still map to their old reasons even though the new keys come first
    for flag, cat in [("Refund/cashback bait with a contact or link", "refund"), ("Asks you to share/enter OTP, PIN or password", "otp"),
                      ("KYC update request", "kyc"), ("URL shortener hides the real link (bit.ly)", "shortener"),
                      ("Courier/parcel fee scam pattern", "courier"), ("Fake prize / lottery pattern", "prize")]:
        assert appmod.code_reasons([flag], "en") == [appmod.R[cat]["en"]], flag


# ---------------- F8: fail-open, rate limit, size limit ----------------
def _cache_files(d):
    return [p for p in d.rglob("*.json")] if d.exists() else []


def test_fail_open_amber_localized_and_never_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "check", _down)
    for lang in ("en", "hi", "gu"):
        r = c.post("/api/check", data={"text": "Hello, lunch at 1?", "lang": lang}).json()
        assert r["verdict"] == "amber" and r["ai_unavailable"] and r["source"] == "code"
        assert r["reasons"] == [appmod.UNCHECKED[lang]] and r["scam_type"] == appmod.TYPE["amber"][lang]
        assert any("1930" in a for a in r["advice"]), lang
    assert "couldn't fully check" in appmod.UNCHECKED["en"] and "1930" in " ".join(appmod.ADV["unchecked"]["en"])
    assert appmod.UNCHECKED["hi"] != appmod.UNCHECKED["en"] != appmod.UNCHECKED["gu"]
    assert _cache_files(tmp_path) == []  # fallback results are never written to the cache
    # and it is not served from cache once the AI is back and says green
    monkeypatch.setattr(llm, "check", lambda *a, **k: (dict(AI_GREEN), "gemini"))
    assert c.post("/api/check", data={"text": "Hello, lunch at 1?", "lang": "en"}).json()["verdict"] == "green"


def test_fail_open_image_only_same_wording(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "check", _down)
    r = c.post("/api/check", files={"image": ("a.png", _png(37), "image/png")}, data={"lang": "gu"}).json()
    assert r["verdict"] == "amber" and r["reasons"] == [appmod.UNCHECKED["gu"]] and _cache_files(tmp_path) == []


def test_fail_open_keeps_code_red_and_ai_green_valid(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "check", _down)
    assert c.post("/api/check", data={"text": KYC}).json()["verdict"] == "red"
    monkeypatch.setattr(llm, "check", lambda *a, **k: (dict(AI_GREEN), "gemini"))
    r = c.post("/api/check", data={"text": "See you at lunch", "lang": "en"}).json()
    assert r["verdict"] == "green" and r["source"] == "gemini"


def test_fail_open_user_key_transient_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(appmod.auth, "enabled", lambda: True)
    monkeypatch.setattr(appmod.auth, "require_user_key", lambda h: "k" * 20)
    monkeypatch.setattr(llm, "check", _down)  # transient failure on the user-key path
    r = c.post("/api/check", data={"text": "See you at lunch", "lang": "en"}).json()
    assert r["verdict"] == "amber" and r["reasons"] == [appmod.UNCHECKED["en"]] and _cache_files(tmp_path) == []


def test_cached_sample_green_stays_green_and_unlimited(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_CHECK", "1")
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    import json
    key = appmod._cache_path(b"", "cached green msg", "en")
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps({**AI_GREEN, "scam_type": ""}))
    for _ in range(5):  # cache hits never count towards / hit the limit
        r = c.post("/api/check", data={"text": "cached green msg", "lang": "en"})
        assert r.status_code == 200 and r.json()["verdict"] == "green" and r.json()["source"] == "cache"


def test_rate_limit_check_429_localized(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_CHECK", "3")
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "check", _down)
    h = {"X-Forwarded-For": "203.0.113.7, 10.0.0.1"}
    for i in range(3):
        assert c.post("/api/check", data={"text": f"msg {i}"}, headers=h).status_code == 200
    r = c.post("/api/check", data={"text": "msg 9", "lang": "hi"}, headers=h)
    j = r.json()
    assert r.status_code == 429 and j["error"] == "rate_limited" and isinstance(j["retry_after"], int) and 1 <= j["retry_after"] <= 61
    assert r.headers["Retry-After"] == str(j["retry_after"]) and str(j["retry_after"]) in j["message"]
    assert "सेकंड" in j["message"]
    assert "સેકન્ડ" in c.post("/api/check", data={"text": "msg 10", "lang": "gu"}, headers=h).json()["message"]
    assert "seconds" in c.post("/api/check", data={"text": "msg 11", "lang": "zz"}, headers=h).json()["message"]
    # another IP (first X-Forwarded-For entry) is unaffected; static/health/config never limited
    assert c.post("/api/check", data={"text": "msg 0"}, headers={"X-Forwarded-For": "198.51.100.9"}).status_code == 200
    for _ in range(10):
        assert c.get("/api/health", headers=h).status_code == 200 and c.get("/api/config", headers=h).status_code == 200


def test_rate_limit_falls_back_to_client_host_and_complaint_bucket(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_CHECK", "1")
    monkeypatch.setenv("RATE_LIMIT_COMPLAINT", "2")
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "check", _down)
    monkeypatch.setattr(appmod.cmp.llm, "draft_text", lambda *a, **k: (_ for _ in ()).throw(llm.LLMUnavailable("x")))
    assert c.post("/api/check", data={"text": "a"}).status_code == 200
    assert c.post("/api/check", data={"text": "b"}).status_code == 429  # no XFF -> request.client.host
    body = {"result": {"verdict": "red", "scam_type": "x", "reasons": [], "red_flags_found": [], "advice": [],
                       "extracted": {"urls": [], "phones": [], "upi_ids": [], "amounts": []}}, "lang": "gu"}
    assert [c.post("/api/complaint", json=body).status_code for _ in range(3)] == [200, 200, 429]
    r = c.post("/api/complaint", json=body)
    assert r.json()["error"] == "rate_limited" and "સેકન્ડ" in r.json()["message"] and "Retry-After" in r.headers


def test_rate_limiter_sliding_window_and_bounded_memory():
    lim = appmod.RateLimiter(window=0.2, max_keys=50)
    assert [lim.hit("check", "1.1.1.1", 2) for _ in range(2)] == [0, 0] and lim.hit("check", "1.1.1.1", 2) >= 1
    import time; time.sleep(0.25)
    assert lim.hit("check", "1.1.1.1", 2) == 0  # window slid
    assert lim.hit("check", "9.9.9.9", 0) == 0  # limit <= 0 disables
    for i in range(500):
        lim.hit("check", f"10.0.{i // 250}.{i % 250}", 5)
    assert len(lim.hits) <= 200


def test_body_too_large_content_length_413(monkeypatch):
    monkeypatch.setattr(appmod, "MAX_BODY", 1000)
    r = c.post("/api/check", data={"text": "x" * 5000}, headers={"Origin": "https://example.org"})
    assert r.status_code == 413 and r.json()["error"] == "too_large" and r.json()["message"]
    assert r.headers.get("access-control-allow-origin") == "*"  # 413 still carries CORS headers
    r = c.post("/api/complaint", content=b"{" + b" " * 5000 + b"}", headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["error"] == "too_large"
    assert c.get("/api/health").status_code == 200  # GET never size-checked


def test_body_too_large_chunked_upload_enforced_while_reading(monkeypatch):
    monkeypatch.setattr(appmod, "MAX_BODY", 1000)
    def gen():
        yield b"text=" + b"a" * 600
        yield b"b" * 600
    r = c.post("/api/check", content=gen(), headers={"content-type": "application/x-www-form-urlencoded"})
    assert r.status_code == 413 and r.json()["error"] == "too_large"


def test_normal_sized_requests_unaffected_by_size_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "check", _down)
    assert appmod.MAX_BODY == appmod.MAX_IMG == 4 * 1024 * 1024
    assert c.post("/api/check", data={"text": "hi"}, files={"image": ("a.png", _png(40), "image/png")}).status_code == 200


def test_f9_pipeline_combine_with_mocked_llm(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)

    def ai(v):
        return lambda *a, **k: ({**AI_GREEN, "verdict": v}, "gemini")
    monkeypatch.setattr(llm, "check", ai("green"))  # weak signal only (urgency) + AI green -> green
    assert c.post("/api/check", data={"text": "Your pack expires today, recharge now to continue", "lang": "en"}).json()["verdict"] == "green"
    monkeypatch.setattr(llm, "check", ai("amber"))  # AI amber is kept
    assert c.post("/api/check", data={"text": "Your pack expires today, recharge now to continue 2", "lang": "en"}).json()["verdict"] == "amber"
    monkeypatch.setattr(llm, "check", ai("green"))  # strong OTP-ask flag is never lowered by an AI green (the reported miss)
    r = c.post("/api/check", data={"text": "Your OTP is 123456, share it with our executive to cancel the transaction.", "lang": "en"}).json()
    assert r["verdict"] == "red"
    r = c.post("/api/check", data={"text": "123456 is your OTP. Do not share it with anyone.", "lang": "en"}).json()
    assert r["verdict"] == "green"
    monkeypatch.setattr(llm, "check", ai("red"))  # AI red is never lowered by the rules
    assert c.post("/api/check", data={"text": "Recharge of Rs 299 successful. Validity 28 days.", "lang": "en"}).json()["verdict"] == "red"
