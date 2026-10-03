# Thagi Pakdo (Scam Checker) - Build Spec
Hack Day Surat. 3-person team, ~90 minutes total. Judged on a 2-minute LIVE DEMO + public GitHub repo created at the event.
Project dir: /workspace/thagi-pakdo   License: Apache-2.0   Python 3.13.

## Product
User uploads a screenshot OR pastes a suspicious SMS/WhatsApp/UPI message.
Output: a big RED / AMBER / GREEN verdict card, 2-4 plain reasons, "what to do" steps (e.g. don't pay, don't click, block, report to cybercrime helpline 1930 / cybercrime.gov.in), in Gujarati / Hindi / English (switcher), with a Read-aloud button.

## Architecture (keep tiny)
- Backend: FastAPI app.py. POST /api/check (multipart: optional image, optional text, lang=gu|hi|en) -> JSON.
- Gemma: google-genai SDK, model `gemma-4-26b-a4b-it` (image BEFORE text, upload image via Files API or Part.from_bytes; if inline bytes fail, use Files API). Ask for strict JSON: {verdict: red|amber|green, scam_type, reasons[], red_flags_found[], extracted: {urls[], phones[], upi_ids[], amounts[]}, advice[]} in the requested language. Parse robustly (strip code fences / thought blocks).
- Plain-code checks (checks.py), NOT the LLM: regex-extract URLs/UPI IDs/phones/amounts from text; flag shorteners (bit.ly, tinyurl...), punycode/lookalike domains, http vs https, suspicious TLDs (.xyz .top .click .cc), urgency words, "KYC", "OTP share", "collect request", fake-prize patterns. Combine: if code flags are strong, never output green; final verdict = max severity of code score and Gemma verdict.
- Local fallback: backend `LLM_BACKEND=gemini|local`; local = OpenAI-compatible endpoint (llama.cpp / Ollama) at LOCAL_BASE_URL running Gemma 4 E4B. Auto-fail over to local on 429/network error; if both fail, return code-only verdict flagged "AI unavailable".
- Cache: sample_cache/ keyed by hash of input so the demo works if rate-limited or offline.
- Frontend: single static page web/index.html (no build step): drag-drop/paste image, textarea, language buttons, big colored verdict card, Read-aloud via browser speechSynthesis (voices lang gu-IN/hi-IN/en-IN; if no voice, hide button gracefully), 4 one-click "Try sample" buttons.
- Agent Skill: skills/scam-check/SKILL.md (Agent Skills spec: frontmatter name == dir name, lowercase-hyphen, description says what + when; optional scripts/check.py CLI). Must validate with `skills-ref validate` if installable, else manually satisfy spec.
- Privacy: free Gemini tier may use inputs to improve Google products -> UI note + only fake samples in demo; --local mode for real messages.

## Samples (fake only) in samples/
4 scams (fake KYC SMS with short link, UPI collect-request "refund", fake courier fee WhatsApp screenshot, lottery/prize) + 1 safe (genuine-looking OTP/bank info alert with no link). Screenshots as PNG + .txt versions.

## Roles / file ownership (avoid conflicts)
- Backend Builder: app.py, checks.py, llm.py, requirements.txt, tests/ (pytest for checks.py)
- Frontend Builder: web/ (index.html, app.js, style.css), samples/ screenshots
- Repo & Demo QA: README.md, LICENSE, .gitignore, skills/, samples/*.txt, demo script, GitHub repo + commits, final end-to-end test
- Manager: plan, review gate, integration

## Definition of done
`pip install -r requirements.txt && uvicorn app:app` serves the page; all 5 samples give correct verdicts in en + at least one of gu/hi; failover works; README has run steps, license, "AI assistants used" credit, what's original; repo public with Apache-2.0.
