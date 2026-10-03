import json, os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
import app as appmod, complaint, llm

c = TestClient(appmod.app)
RES = {"verdict": "red", "scam_type": "UPI refund scam", "reasons": ["Never enter PIN to receive money"], "red_flags_found": ["collect request"],
       "extracted": {"urls": ["http://bad.xyz/pay"], "phones": ["+91 98250 11234"], "upi_ids": ["refund.help@okaxis"], "amounts": ["4999"]},
       "source": "cache", "code_score": 5}
DET = {"name": "Asha Shah", "phone": "9000000000", "date_time": "3 Oct 2026 10:00", "amount_lost": "Rs 4,999", "payment_method": "UPI",
       "transaction_id": "T123456", "what_happened": "I approved a collect request."}


@pytest.fixture(autouse=True)
def tmpcache(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "draft_text", lambda *a, **k: (_ for _ in ()).throw(llm.LLMUnavailable("down")))
    return tmp_path


@pytest.mark.parametrize("lang", ["en", "hi", "gu"])
def test_template_all_langs_facts_and_placeholders(lang):
    r = c.post("/api/complaint", json={"result": RES, "lang": lang}).json()
    assert r["source"] == "template" and r["portal_url"] == "https://cybercrime.gov.in" and r["helpline"] == "1930"
    for fact in ("http://bad.xyz/pay", "+91 98250 11234", "refund.help@okaxis", "4999", "UPI refund scam"):
        assert fact in r["body"]
    assert complaint.PH[lang]["name"] in r["body"] and r["subject"]
    assert r["missing_fields"] == list(complaint.FIELDS)


@pytest.mark.parametrize("lang", ["en", "hi", "gu"])
def test_template_with_details_has_no_placeholders(lang):
    r = c.post("/api/complaint", json={"result": RES, "lang": lang, "details": DET}).json()
    assert r["missing_fields"] == [] and "[" not in r["body"]
    for v in DET.values():
        assert v in r["body"]


def test_missing_fields_partial_and_blank_values():
    r = c.post("/api/complaint", json={"result": RES, "details": {"name": "A", "phone": "  ", "amount_lost": None}}).json()
    assert "name" not in r["missing_fields"] and "phone" in r["missing_fields"] and "amount_lost" in r["missing_fields"]


@pytest.mark.parametrize("body", [{}, {"result": "x"}, {"result": {"verdict": "purple"}}, {"result": RES, "lang": "fr"}, {"result": RES, "details": "str"}])
def test_bad_body(body):
    assert c.post("/api/complaint", json=body).status_code == 422


def test_no_cache_write_when_details_present(tmpcache, monkeypatch):
    ok = lambda p, v, **k: (v(json.dumps({"subject": "S", "body": "B" * 100 + " http://bad.xyz/pay +91 98250 11234 refund.help@okaxis"})), "gemini")
    monkeypatch.setattr(llm, "draft_text", ok)
    r = c.post("/api/complaint", json={"result": RES, "lang": "en", "details": DET}).json()
    assert r["source"] == "gemini"
    assert not (tmpcache / "complaints").exists()
    c.post("/api/complaint", json={"result": RES, "lang": "en"})  # no details -> cached
    assert len(list((tmpcache / "complaints").glob("*.json"))) == 1


def test_mocked_llm_path_cache_and_prompt(tmpcache, monkeypatch):
    seen = []
    def fake(prompt, v, **k):
        seen.append(prompt)
        return v('```json\n{"subject":"Subj [name]","body":"' + "Dear sir " * 20 + ' Name: [name], when: [date_time]"}\n```'), "gemini"
    monkeypatch.setattr(llm, "draft_text", fake)
    r = c.post("/api/complaint", json={"result": RES, "lang": "gu"}).json()
    assert r["source"] == "gemini" and "[name]" not in r["body"] and "[તમારું નામ]" in r["subject"]
    assert "[ઘટનાની તારીખ અને સમય]" in r["body"]
    for fact in ("http://bad.xyz/pay", "+91 98250 11234", "refund.help@okaxis"):  # dropped identifiers re-appended
        assert fact in r["body"]
    assert "Gujarati" in seen[0] and "NEVER invent" in seen[0]
    monkeypatch.setattr(llm, "draft_text", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must hit cache")))
    r2 = c.post("/api/complaint", json={"result": {**RES, "source": "gemini"}, "lang": "gu"}).json()
    assert r2["body"] == r["body"]  # cache key ignores 'source'


def test_bad_llm_output_falls_back_to_template(monkeypatch):
    def draft(prompt, v, **k):
        v("not json")  # raises ValueError -> propagate like llm would after retries
    monkeypatch.setattr(complaint.llm, "draft_text", lambda p, v, **k: (_ for _ in ()).throw(llm.LLMUnavailable("parse")))
    assert c.post("/api/complaint", json={"result": RES, "lang": "en"}).json()["source"] == "template"
    with pytest.raises(ValueError):
        complaint._validator(RES, "en")("not json")
    with pytest.raises(ValueError):
        complaint._validator(RES, "en")('{"subject":"s","body":"short"}')


def test_draft_text_retry_and_failover(monkeypatch):
    import importlib
    real = importlib.reload(llm).draft_text  # undo the autouse stub
    seq = iter(["garbage", '{"subject":"s","body":"' + "x" * 90 + '"}'])
    monkeypatch.setattr(llm, "_gemini", lambda *a, **k: next(seq))
    v = complaint._validator({**RES, "extracted": {}}, "en")
    out, src = real("p", v)
    assert src == "gemini" and out["subject"] == "s"
    def boom(*a, **k): raise RuntimeError("400 bad")
    monkeypatch.setattr(llm, "_gemini", boom)
    monkeypatch.setattr(llm, "_local", lambda *a, **k: '{"subject":"s","body":"' + "y" * 90 + '"}')
    assert real("p", v)[1] == "local"


@pytest.mark.parametrize("lang", ["en", "hi", "gu"])
def test_filled_values_plain_in_gemma_path(monkeypatch, lang):
    body = "Dear sir " * 12 + " Name: [Test User], phone [9000000000], lost 【Rs 4,999】 ( Test User ) " + "[Test User] [name] [date_time]"
    monkeypatch.setattr(llm, "draft_text", lambda p, v, **k: (v(json.dumps({"subject": "Complaint by [Test User]", "body": body})), "gemini"))
    r = c.post("/api/complaint", json={"result": RES, "lang": lang, "details": {"name": "Test User", "phone": "9000000000", "amount_lost": "Rs 4,999"}}).json()
    assert "[Test User]" not in r["body"] and "[9000000000]" not in r["body"] and "【" not in r["body"]
    assert "Name: Test User" in r["body"] and "Complaint by Test User" == r["subject"]
    assert complaint.PH[lang]["date_time"] in r["body"] and "[name]" not in r["body"]  # unfilled stay bracketed


@pytest.mark.parametrize("lang", ["en", "hi", "gu"])
def test_filled_values_plain_in_template(lang):
    r = c.post("/api/complaint", json={"result": RES, "lang": lang, "details": {"name": "Test User"}}).json()
    assert "Test User" in r["body"] and "[Test User]" not in r["body"] and complaint.PH[lang]["phone"] in r["body"]
