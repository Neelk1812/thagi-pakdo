import os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import llm

BASE = '{"verdict":"RED","scam_type":"fake KYC","reasons":["a","b"],"red_flags_found":["x"],"extracted":{"urls":["bit.ly/x"],"phones":[],"upi_ids":[],"amounts":["Rs 5"]},"advice":["Call 1930"]}'


def test_plain():
    d = llm.parse_json(BASE)
    assert d["verdict"] == "red" and d["extracted"]["urls"] == ["bit.ly/x"] and d["advice"] == ["Call 1930"]


def test_fenced():
    assert llm.parse_json("```json\n" + BASE + "\n```")["verdict"] == "red"


def test_think_blocks_with_braces():
    raw = "<think>maybe {\"verdict\": \"green\"} hmm</think>\nHere:\n" + BASE + "\nthanks"
    assert llm.parse_json(raw)["verdict"] == "red"


def test_prose_around_and_braces_in_strings():
    raw = 'Sure! {"verdict":"amber","reasons":["uses } brace","ok"],"advice":"block"} done'
    d = llm.parse_json(raw)
    assert d["verdict"] == "amber" and d["reasons"][0] == "uses } brace" and d["advice"] == ["block"]
    assert d["extracted"] == {"urls": [], "phones": [], "upi_ids": [], "amounts": []}


def test_unicode_gujarati():
    d = llm.parse_json('{"verdict":"red","reasons":["આ છેતરપિંડી છે"]}')
    assert d["reasons"] == ["આ છેતરપિંડી છે"]


@pytest.mark.parametrize("bad", ["", None, "no json", '{"verdict":"purple"}', "[1,2]", '{"verdict": "red"'])
def test_bad(bad):
    with pytest.raises(ValueError):
        llm.parse_json(bad)


def test_failover_all_fail(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LOCAL_BASE_URL", "http://127.0.0.1:1/v1")
    with pytest.raises(llm.LLMUnavailable):
        llm.check("hi")


def test_failover_to_local(monkeypatch):
    def boom(*a): raise RuntimeError("429")
    monkeypatch.setitem(llm.BACKENDS, "gemini", boom)
    monkeypatch.setitem(llm.BACKENDS, "local", lambda *a: BASE)
    d, src = llm.check("x")
    assert src == "local" and d["verdict"] == "red"


def test_shrink_image_downscales_to_jpeg():
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGBA", (720, 2000), (255, 0, 0, 255)).save(buf, "PNG")
    data, mime = llm.shrink_image(buf.getvalue(), "image/png")
    im = Image.open(io.BytesIO(data))
    assert mime == "image/jpeg" and max(im.size) <= 1024 and im.size[1] == 1024


def test_shrink_image_bad_bytes_passthrough():
    assert llm.shrink_image(b"not an image", "image/png") == (b"not an image", "image/png")


def test_transient_detection():
    assert llm._is_transient(Exception("429 RESOURCE_EXHAUSTED"))
    assert llm._is_transient(Exception("The read operation timed out"))
    assert not llm._is_transient(Exception("400 INVALID_ARGUMENT bad image"))


def test_retry_once_on_parse_failure(monkeypatch):
    seq = iter(["not json at all", BASE]); calls = []
    monkeypatch.setitem(llm.BACKENDS, "gemini", lambda *a: (calls.append(a), next(seq))[1])
    d, src = llm.check("x")
    assert src == "gemini" and d["verdict"] == "red" and len(calls) == 2


def test_retry_on_transient_then_failover_total_bounded(monkeypatch):
    import time
    n = []
    def boom(*a): n.append(1); raise RuntimeError("429 RESOURCE_EXHAUSTED")
    monkeypatch.setitem(llm.BACKENDS, "gemini", boom)
    monkeypatch.setitem(llm.BACKENDS, "local", lambda *a: BASE)
    t = time.time(); d, src = llm.check("x")
    assert src == "local" and len(n) == 2 and time.time() - t < 3


def test_non_transient_error_no_retry(monkeypatch):
    n = []
    def boom(*a): n.append(1); raise RuntimeError("400 INVALID_ARGUMENT")
    monkeypatch.setitem(llm.BACKENDS, "gemini", boom)
    monkeypatch.setitem(llm.BACKENDS, "local", lambda *a: BASE)
    llm.check("x"); assert len(n) == 1


def test_describe_scrubs_key():
    assert "AIza" not in llm._describe(RuntimeError("bad key AIzaSyA1234567890abcdefghijKLMN"))
