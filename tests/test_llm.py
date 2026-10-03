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


# ---------------- F9b: 429/503/timeout retry + optional GEMINI_API_KEY_2 failover ----------------
K1, K2, KU = "AIzaSyPRIMARY0000000000000000000001", "AIzaSyFAILOVR0000000000000000000002", "AIzaSyUSERKEY0000000000000000000003"


@pytest.fixture
def clock(monkeypatch):
    """Fake clock: sleep() advances it, so budget logic is tested instantly."""
    t = [1000.0]; sleeps = []
    monkeypatch.setattr(llm.time, "time", lambda: t[0])
    monkeypatch.setattr(llm.time, "sleep", lambda s: (sleeps.append(s), t.__setitem__(0, t[0] + s)))
    return t, sleeps


def _gem(monkeypatch, clock, script, cost=2.0):
    """script: list of outcomes (str result or Exception) consumed per call; records (api_key kwarg) per call."""
    t, _ = clock; seen = []; it = iter(script)
    def fake(text, image, mime, lang, timeout_s=None, **kw):
        seen.append(kw.get("api_key")); t[0] += cost
        o = next(it)
        if isinstance(o, Exception):
            raise o
        return o
    monkeypatch.setitem(llm.BACKENDS, "gemini", fake)
    return seen


def test_429_then_success_one_retry_with_jitter(monkeypatch, clock):
    monkeypatch.setenv("GEMINI_API_KEY", K1)
    seen = _gem(monkeypatch, clock, [RuntimeError("429 RESOURCE_EXHAUSTED"), BASE])
    d, src = llm.check("x")
    assert src == "gemini" and d["verdict"] == "red" and seen == [None, None]  # primary twice
    assert len(clock[1]) == 1 and 0.8 <= clock[1][0] <= 1.4


def test_503_and_timeout_are_retried(monkeypatch, clock):
    monkeypatch.setenv("GEMINI_API_KEY", K1)
    for err in (RuntimeError("503 UNAVAILABLE"), TimeoutError("The read operation timed out")):
        seen = _gem(monkeypatch, clock, [err, BASE])
        assert llm.check("x")[1] == "gemini" and len(seen) == 2


def test_key2_failover_after_primary_retry(monkeypatch, clock):
    monkeypatch.setenv("GEMINI_API_KEY", K1); monkeypatch.setenv("GEMINI_API_KEY_2", K2)
    seen = _gem(monkeypatch, clock, [RuntimeError("429 RESOURCE_EXHAUSTED"), RuntimeError("429 RESOURCE_EXHAUSTED"), BASE])
    d, src = llm.check("x")
    assert src == "gemini" and seen == [None, None, K2]  # primary, primary retry, then key 2 once
    assert len(clock[1]) == 1  # only the same-key retry pauses


def test_429_everywhere_falls_to_local_within_budget(monkeypatch, clock):
    monkeypatch.setenv("GEMINI_API_KEY", K1); monkeypatch.setenv("GEMINI_API_KEY_2", K2)
    seen = _gem(monkeypatch, clock, [RuntimeError("429 RESOURCE_EXHAUSTED")] * 5)
    monkeypatch.setitem(llm.BACKENDS, "local", lambda *a: BASE)
    t0 = clock[0][0]
    d, src = llm.check("x")
    assert src == "local" and len(seen) == 3 and clock[0][0] - t0 < llm.TOTAL_BUDGET
    monkeypatch.setitem(llm.BACKENDS, "local", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    _gem(monkeypatch, clock, [RuntimeError("429 RESOURCE_EXHAUSTED")] * 5)
    with pytest.raises(llm.LLMUnavailable) as ei:  # code-only fallback happens in app.py on this exception
        llm.check("x")
    assert K1 not in str(ei.value) and K2 not in str(ei.value)


def test_retry_skipped_when_budget_is_short(monkeypatch, clock):
    monkeypatch.setenv("GEMINI_API_KEY", K1); monkeypatch.setenv("GEMINI_API_KEY_2", K2)
    monkeypatch.setattr(llm, "TOTAL_BUDGET", 6.0)
    seen = _gem(monkeypatch, clock, [RuntimeError("429 RESOURCE_EXHAUSTED")] * 5, cost=2.5)
    monkeypatch.setitem(llm.BACKENDS, "local", lambda *a: BASE)
    assert llm.check("x")[1] == "local" and len(seen) == 1 and clock[1] == []  # no budget for pause + retry


def test_no_key2_means_no_failover_and_non_transient_not_retried(monkeypatch, clock):
    monkeypatch.setenv("GEMINI_API_KEY", K1); monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    seen = _gem(monkeypatch, clock, [RuntimeError("429 RESOURCE_EXHAUSTED")] * 3)
    monkeypatch.setitem(llm.BACKENDS, "local", lambda *a: BASE)
    assert llm.check("x")[1] == "local" and seen == [None, None]
    monkeypatch.setenv("GEMINI_API_KEY_2", K2)
    seen = _gem(monkeypatch, clock, [RuntimeError("400 INVALID_ARGUMENT")])
    assert llm.check("x")[1] == "local" and seen == [None]  # a real error is not retried and does not burn key 2


def test_byo_key_path_unaffected_by_key2(monkeypatch, clock):
    monkeypatch.setenv("GEMINI_API_KEY", K1); monkeypatch.setenv("GEMINI_API_KEY_2", K2)
    seen = _gem(monkeypatch, clock, [RuntimeError("429 RESOURCE_EXHAUSTED")] * 3)
    monkeypatch.setitem(llm.BACKENDS, "local", lambda *a: BASE)
    with pytest.raises(llm.UserKeyError) as ei:
        llm.check("x", api_key=KU)
    assert ei.value.code == "gemini_rate_limited" and seen == [KU, KU]  # user key retried once; never server key, key 2 or local
    seen = _gem(monkeypatch, clock, [RuntimeError("API key not valid. API_KEY_INVALID")] * 3)
    with pytest.raises(llm.UserKeyError) as ei:
        llm.check("x", api_key=KU)
    assert ei.value.code == "gemini_key_invalid" and seen == [KU]  # invalid key => explicit error at once
    seen = _gem(monkeypatch, clock, [RuntimeError("429 RESOURCE_EXHAUSTED"), BASE])
    assert llm.check("x", api_key=KU)[1] == "gemini" and seen == [KU, KU]


def test_complaint_draft_text_uses_same_retry_and_failover(monkeypatch, clock):
    monkeypatch.setenv("GEMINI_API_KEY", K1); monkeypatch.setenv("GEMINI_API_KEY_2", K2)
    t, _ = clock; seen = []; it = iter([RuntimeError("503 UNAVAILABLE"), RuntimeError("429 RESOURCE_EXHAUSTED"), "drafted"])
    def fake(text, image, mime, lang, timeout_s=None, prompt=None, max_tokens=None, **kw):
        seen.append(kw.get("api_key")); t[0] += 2
        o = next(it)
        if isinstance(o, Exception):
            raise o
        return o
    monkeypatch.setattr(llm, "_gemini", fake)
    v, src = llm.draft_text("p", lambda raw: raw)
    assert (v, src) == ("drafted", "gemini") and seen == [None, None, K2]
    # BYO key: no key 2
    it = iter([RuntimeError("429 RESOURCE_EXHAUSTED")] * 3); seen.clear()
    with pytest.raises(llm.UserKeyError):
        llm.draft_text("p", lambda raw: raw, api_key=KU)
    assert seen == [KU, KU]


def test_key2_never_logged(monkeypatch, clock, caplog):
    monkeypatch.setenv("GEMINI_API_KEY", K1); monkeypatch.setenv("GEMINI_API_KEY_2", K2)
    seen = _gem(monkeypatch, clock, [RuntimeError(f"429 RESOURCE_EXHAUSTED key={K1}"), RuntimeError(f"429 bad {K2}"), BASE])
    with caplog.at_level("INFO", logger="thagi.llm"):
        llm.check("x")
    text = caplog.text
    assert K1 not in text and K2 not in text and "429" in text and "key=key2" in text
