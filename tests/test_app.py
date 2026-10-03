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
    big = ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * (9 * 1024 * 1024), "image/png")
    assert c.post("/api/check", files={"image": big}).status_code == 400
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
    # code-only green fallback too
    monkeypatch.setattr(llm, "check", _down)
    r = c.post("/api/check", data={"text": "Hello, lunch at 1?", "lang": "hi"}).json()
    assert r["verdict"] == "green" and r["scam_type"] == ""
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
