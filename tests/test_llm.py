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
