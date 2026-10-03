import json, logging, os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
import app as appmod, auth, llm

c = TestClient(appmod.app)
TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJlMTIz"
USER_KEY = "AIzaSyUSERKEY0123456789abcdefghijk"
SERVER_KEY = "AIzaSySERVERKEY987654321zyxwvutsrqp"
KYC = "Your KYC is pending, account blocked today. Update: http://bit.ly/x1"
AI = json.dumps({"verdict": "red", "scam_type": "KYC", "reasons": ["r"], "red_flags_found": ["f"], "advice": ["a"],
                 "extracted": {"urls": [], "phones": [], "upi_ids": [], "amounts": []}})
RES = {"verdict": "red", "scam_type": "KYC", "reasons": ["r"], "red_flags_found": [], "extracted": {"urls": ["http://bit.ly/x1"], "phones": [], "upi_ids": [], "amounts": []}}
GOOD = {"Authorization": f"Bearer {TOKEN}", "X-Gemini-Key": USER_KEY}


class FakeClient:
    instances, behavior = [], None

    def __init__(self, api_key=None, **kw):
        self.api_key = api_key
        FakeClient.instances.append(self)
        outer = self

        class M:
            def generate_content(self, model, contents, config):
                if FakeClient.behavior:
                    raise FakeClient.behavior
                return type("R", (), {"text": AI})()
        self.models = M()


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GEMINI_API_KEY", SERVER_KEY)
    calls = []
    def verify(tok):
        calls.append(tok)
        if tok != TOKEN:
            raise ValueError("bad token")
        return {"email": "a@b.com", "email_verified": True, "aud": "cid.apps.googleusercontent.com"}
    monkeypatch.setattr(auth, "verify_google_token", verify)
    from google import genai
    FakeClient.instances, FakeClient.behavior = [], None
    monkeypatch.setattr(genai, "Client", FakeClient)
    return calls


def post(headers=None, text=KYC, **kw):
    return c.post("/api/check", data={"text": text, "lang": "en"}, headers=headers or {}, **kw)


def test_config_both_modes(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    assert c.get("/api/config").json() == {"auth_required": False, "google_client_id": None}
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "  ")
    assert c.get("/api/config").json() == {"auth_required": False, "google_client_id": None}
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "abc.apps.googleusercontent.com")
    assert c.get("/api/config").json() == {"auth_required": True, "google_client_id": "abc.apps.googleusercontent.com"}


def test_disabled_mode_unchanged(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    seen = []
    monkeypatch.setattr(llm, "check", lambda *a, **k: (seen.append((a, k)), (json.loads(AI), "gemini"))[1])
    r = post()  # no headers at all
    assert r.status_code == 200 and r.json()["source"] == "gemini"
    assert seen[0][1] == {}  # llm.check called exactly as before (no api_key)
    r = c.post("/api/complaint", json={"result": RES, "lang": "en"})
    assert r.status_code == 200 and r.json()["source"] == "template"


def test_cache_hit_open_miss_requires_login(on):
    appmod.CACHE.mkdir(parents=True, exist_ok=True)
    appmod._cache_path(b"", KYC, "en").write_text(json.dumps({**json.loads(AI), "verdict": "red", "lang": "en"}))
    r = post()
    assert r.status_code == 200 and r.json()["source"] == "cache"
    r = post(text="a brand new message")
    assert r.status_code == 401 and r.json() == {"error": "login_required", "message": r.json()["message"]} and r.json()["message"]
    assert post({"Authorization": "  "}, text="again new").json()["error"] == "login_required"
    assert FakeClient.instances == [] and on == []


def test_sample_path_open(on):
    png = (appmod.SAMPLES / "kyc_sms.png").read_bytes(); txt = (appmod.SAMPLES / "kyc_sms.txt").read_text(encoding="utf-8")
    appmod.CACHE.mkdir(parents=True, exist_ok=True)
    appmod._cache_path(png, txt, "en").write_text(json.dumps({**json.loads(AI), "lang": "en"}))
    r = c.post("/api/check", files={"image": ("k.png", png, "image/png")}, data={"lang": "en"})
    assert r.status_code == 200 and r.json()["source"] == "cache"


@pytest.mark.parametrize("hdr", ["Bearer wrong", "Basic abc", "Bearer", "Bearer   "])
def test_bad_token(on, hdr):
    r = post({"Authorization": hdr, "X-Gemini-Key": USER_KEY}, text="new " + hdr)
    assert r.status_code == 401 and r.json()["error"] in ("invalid_token", "login_required")
    if hdr.startswith(("Bearer wrong", "Basic")):
        assert r.json()["error"] == "invalid_token"


def test_unverified_email_and_expired(on, monkeypatch):
    monkeypatch.setattr(auth, "verify_google_token", lambda t: {"email_verified": False})
    assert post(GOOD, text="n1").json()["error"] == "invalid_token"
    def expired(t): raise ValueError("Token expired")
    monkeypatch.setattr(auth, "verify_google_token", expired)
    r = post(GOOD, text="n2")
    assert r.status_code == 401 and r.json()["error"] == "invalid_token"


def test_good_token_no_key_402(on):
    r = post({"Authorization": f"Bearer {TOKEN}"}, text="n3")
    assert r.status_code == 402 and r.json()["error"] == "key_required"
    r = post({"Authorization": f"Bearer {TOKEN}", "X-Gemini-Key": "  "}, text="n4")
    assert r.status_code == 402


def test_user_key_per_request_client_never_server_key(on):
    r = post(GOOD, text="fresh one")
    assert r.status_code == 200 and r.json()["source"] == "gemini" and r.json()["verdict"] == "red"
    assert [i.api_key for i in FakeClient.instances] == [USER_KEY]
    r = c.post("/api/check", data={"text": "fresh two", "lang": "en"}, headers={**GOOD, "X-Gemini-Key": "AIzaSyOTHERUSERKEY0000000000000000"})
    assert [i.api_key for i in FakeClient.instances][-1] == "AIzaSyOTHERUSERKEY0000000000000000"
    assert SERVER_KEY not in [i.api_key for i in FakeClient.instances]
    # result cached by content only: same content, no auth -> served from cache
    assert post(text="fresh one").json()["source"] == "cache"
    # cache key/files never contain the key or token
    blob = "".join(p.name + p.read_text() for p in appmod.CACHE.glob("*.json"))
    assert USER_KEY not in blob and TOKEN not in blob


def test_invalid_key_and_rate_limit_are_explicit_errors(on):
    FakeClient.behavior = RuntimeError("400 INVALID_ARGUMENT. API key not valid. Please pass a valid API key.")
    r = post(GOOD, text="k1")
    assert r.status_code == 400 and r.json()["error"] == "gemini_key_invalid" and r.json()["message"]
    FakeClient.behavior = RuntimeError("403 PERMISSION_DENIED")
    assert post(GOOD, text="k2").json()["error"] == "gemini_key_invalid"
    FakeClient.behavior = RuntimeError("429 RESOURCE_EXHAUSTED quota")
    r = post(GOOD, text="k3")
    assert r.status_code == 429 and r.json()["error"] == "gemini_rate_limited"
    assert SERVER_KEY not in [i.api_key for i in FakeClient.instances] and all(i.api_key == USER_KEY for i in FakeClient.instances)


def test_transient_failure_falls_back_to_code_only(on):
    FakeClient.behavior = RuntimeError("503 UNAVAILABLE overloaded")
    r = post(GOOD, text="Your KYC is pending, blocked today http://bit.ly/zz")
    assert r.status_code == 200 and r.json()["ai_unavailable"] is True and r.json()["source"] == "code"


def test_complaint_auth_flow(on, monkeypatch):
    r = c.post("/api/complaint", json={"result": RES, "lang": "en", "details": {"name": "X"}})
    assert r.status_code == 401 and r.json()["error"] == "login_required"
    r = c.post("/api/complaint", json={"result": RES, "lang": "en"}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 402
    captured = {}
    def draft(prompt, v, **k):
        captured.update(k); return v(json.dumps({"subject": "s", "body": "b" * 100 + " http://bit.ly/x1"})), "gemini"
    monkeypatch.setattr(llm, "draft_text", draft)
    r = c.post("/api/complaint", json={"result": RES, "lang": "en"}, headers=GOOD)
    assert r.status_code == 200 and captured == {"api_key": USER_KEY}
    # cached (no details) -> now open without auth
    monkeypatch.setattr(llm, "draft_text", lambda *a, **k: (_ for _ in ()).throw(AssertionError("cache expected")))
    assert c.post("/api/complaint", json={"result": RES, "lang": "en"}).status_code == 200


def test_complaint_user_key_errors(on):
    FakeClient.behavior = RuntimeError("API key not valid")
    r = c.post("/api/complaint", json={"result": RES, "lang": "en"}, headers=GOOD)
    assert r.status_code == 400 and r.json()["error"] == "gemini_key_invalid"
    FakeClient.behavior = RuntimeError("503 UNAVAILABLE")
    r = c.post("/api/complaint", json={"result": RES, "lang": "hi", "details": {"name": "Z"}}, headers=GOOD)
    assert r.status_code == 200 and r.json()["source"] == "template"


def test_cors_preflight_allows_auth_headers(on):
    r = c.options("/api/check", headers={"Origin": "http://phone", "Access-Control-Request-Method": "POST",
                                         "Access-Control-Request-Headers": "authorization,x-gemini-key,content-type"})
    allowed = r.headers["access-control-allow-headers"].lower()
    assert r.status_code == 200 and "authorization" in allowed and "x-gemini-key" in allowed
    assert c.post("/api/check", data={"text": "n"}, headers={"Origin": "http://phone"}).headers["access-control-allow-origin"] == "*"


def test_no_secrets_in_logs(on, caplog):
    caplog.set_level(logging.DEBUG)
    FakeClient.behavior = RuntimeError(f"400 API key not valid: {USER_KEY} Authorization: Bearer {TOKEN}")
    r = post(GOOD, text="log test one")
    FakeClient.behavior = RuntimeError(f"503 UNAVAILABLE key={USER_KEY} Bearer {TOKEN}")
    post(GOOD, text="log test two")
    logging.getLogger("x.test").warning("leak? %s and Bearer %s", USER_KEY, TOKEN)
    out = caplog.text + r.text
    assert USER_KEY not in out and TOKEN not in out and SERVER_KEY not in out
    assert "<key>" in out or "Bearer <token>" in out or "<jwt>" in out


def test_scrub_covers_patterns():
    s = llm.scrub(f"k={USER_KEY} h=Bearer {TOKEN} jwt {TOKEN} x-gemini-key: abcdef1234567890")
    assert USER_KEY not in s and TOKEN not in s and "abcdef1234567890" not in s
