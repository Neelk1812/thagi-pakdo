# Thagi Pakdo (ઠગી પકડો) - Scam Checker

Paste a suspicious SMS / WhatsApp / UPI message, or upload a screenshot of it, and get a big **RED / AMBER / GREEN** verdict, 2 to 4 plain-language reasons, and "what to do" steps (don't pay, don't click, block, report to **1930** / [cybercrime.gov.in](https://cybercrime.gov.in)). Works in **Gujarati, Hindi and English**, with a **Read-aloud** button for people who find reading hard.

Built for Hack Day Surat. "Thagi Pakdo" means "catch the con".

> Status: draft written during the event. Items marked **[unverified]** have not yet been tested end to end.

## How it works

1. **Plain-code checks (`checks.py`)** - no AI. Regex extraction of URLs, UPI IDs, phone numbers and amounts, plus flags for URL shorteners, lookalike/punycode domains, `http://`, suspicious TLDs (.xyz, .top, .click ...), urgency words, fake KYC, OTP/PIN requests, UPI collect requests, fake prizes and courier fees.
2. **Gemma (`llm.py`)** - reads the message or screenshot and returns strict JSON (verdict, scam type, reasons, advice) in the chosen language.
3. **Combine** - the final verdict is the more severe of the code score and the Gemma verdict, so strong code flags can never be turned into green by the AI.
4. **Fallbacks** - if Gemini fails (rate limit / network), it fails over to a local Gemma server; if both fail, you get a code-only verdict marked "AI unavailable". Results are cached in `sample_cache/` so the demo works offline or when rate-limited.

## Run it

Developed and tested with Python 3.13 (other versions untested).

```bash
git clone https://github.com/Neelk1812/thagi-pakdo && cd thagi-pakdo
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # then put your GEMINI_API_KEY in .env
uvicorn app:app
```

Without a key the app still runs: cached samples are served from `sample_cache/`, and anything else falls back to a local Gemma server (if configured) or to the rules-only verdict marked "AI unavailable".

Open http://127.0.0.1:8000. Check http://127.0.0.1:8000/api/health to see which backend is configured.

### Configuration (environment variables / `.env`)

Copy `.env.example` to `.env` and fill it in (`.env` is git-ignored; never commit keys). `app.py` has a small built-in `.env` loader (no python-dotenv needed) that runs at startup. Variables already set in your real environment take priority over `.env`. Lines are `KEY=VALUE`; `#` comments are allowed.

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | none | Google AI Studio key for the hosted Gemma model |
| `GEMINI_MODEL` | `gemma-4-26b-a4b-it` | Hosted model name |
| `LLM_BACKEND` | `gemini` | `gemini` = Gemini first, fail over to local; `local` = local only |
| `LOCAL_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible endpoint (Ollama or llama.cpp server) |
| `LOCAL_MODEL` | `gemma4:e4b` | Model name served locally |
| `LOCAL_API_KEY` | `local` | Bearer token sent to the local server (usually ignored) |
| `GEMINI_TIMEOUT_MS` / `LOCAL_TIMEOUT` | `30000` / `120` | Timeouts |

### Local mode (real messages stay on your machine)

Run Gemma 4 E4B behind an OpenAI-compatible server, then point the app at it:

```bash
# Ollama (default port 11434)
ollama pull gemma4:e4b          # [unverified] check the exact model tag on your Ollama
# or llama.cpp: llama-server -m <gemma-4-e4b.gguf> --port 8080

LLM_BACKEND=local LOCAL_BASE_URL=http://localhost:11434/v1 LOCAL_MODEL=gemma4:e4b uvicorn app:app
```

Local mode is selected with `LLM_BACKEND=local`. It has **not been tested with a real Gemma 4 E4B model [unverified]**; the local code path was only checked against a stub OpenAI-compatible server and unit tests.

## Speed and test status

Measured on 3 Oct 2026 from a clean clone (server and client on the same machine, hosted Gemma over the internet):

| Case | Time |
|---|---|
| Cached result (same image + text + language) | about 2 ms |
| Live Gemma call, text only | about 2.4 to 5 s |
| Live Gemma call, screenshot (with or without text) | about 4.5 to 5 s |
| Gemini unreachable/bad key, rules-only answer | under 0.5 s |

The cache key is the exact image bytes + text + language, so a different screenshot or even edited text is a live call. The committed `sample_cache/` covers the 5 fake samples sent as screenshot + text in en, hi and gu.

Verified: all 5 samples (4 scams red, the safe OTP green) in en, hi and gu; image upload; a bad Gemini key falls back to the rules-only verdict ("AI unavailable"); failover to a local OpenAI-compatible endpoint works (tested against a stub server). **Not verified:** a real Gemma 4 E4B local model, and read-aloud voices on other machines. Run `pytest` for the unit tests.

## Privacy

- With the **free Gemini tier, Google may use inputs to improve its products.** Do not paste real personal messages while using the hosted model.
- The demo uses **only fake samples** (`samples/`).
- For real messages, run locally with `LLM_BACKEND=local` so nothing leaves your machine.
- The app itself stores nothing except cached results for already-checked inputs in `sample_cache/`. The cache committed in this repo was generated from the fake samples only; your own checks will add files there, so don't commit them.

## Agent Skill

`skills/scam-check/` is an [Agent Skills](https://agentskills.io) skill so any compatible AI agent can run the same checks.

```bash
python skills/scam-check/scripts/check.py "Your SBI account will be blocked today. Update KYC: http://bit.ly/abc"
python skills/scam-check/scripts/check.py --file samples/kyc_sms.txt
```

It prints JSON (`verdict`, `score`, `reasons`, `extracted`, `advice`) and exits 0 / 1 / 2 for green / amber / red. It is offline and rule-based only. Validated with the reference validator: `pip install skills-ref && agentskills validate skills/scam-check` (the installed command is named `agentskills`).

## Samples (fake only)

`samples/` holds 5 fake messages as `.txt` and `.png`: a KYC SMS with a short link, a UPI collect-request "refund", a courier-fee message, a KBC lottery message, and one genuine-looking bank OTP alert (should be GREEN). All phone numbers, UPI IDs and links are made up.

## Project layout

```
app.py            FastAPI app: POST /api/check, GET /api/health, serves web/ and /samples
checks.py         Plain-code scam checks and severity scoring (no AI)
llm.py            Gemini / local Gemma backends, JSON parsing, failover
web/              Static front end (index.html, app.js, style.css), no build step
samples/          Fake sample messages (.txt) and screenshots (.png)
scripts/prewarm.py  Fills sample_cache/ by running every sample (en/hi/gu) through /api/check
sample_cache/     Cached results keyed by input hash (fake samples only are committed)
.env.example      Template for configuration (copy to .env)
skills/scam-check/  Agent Skill (SKILL.md + scripts/check.py)
tests/            pytest tests
DEMO_SCRIPT.md    2-minute live demo script
```

Run the tests with `pytest`.

## What's original

All code, the UI, the samples and the Agent Skill in this repo were written during the event. That includes the rule-based scam checks tuned to Indian fraud patterns (KYC links, UPI collect requests, courier/India Post fees, KBC-style prizes), the "code can raise but AI can't lower" verdict combination, the Gemini-to-local failover with a code-only last resort, the cache, the Gujarati / Hindi / English front end with read-aloud, and the fake sample messages and screenshots.

Third-party pieces we use (not written by us): FastAPI, uvicorn, python-multipart, httpx and the google-genai SDK at run time, and pytest for tests (see `requirements.txt`). At run time the app calls **Gemma 4 (`gemma-4-26b-a4b-it`) via Google AI Studio**, or Gemma 4 E4B locally, under Google's terms for those models.

## AI assistants used

Built with AI coding agents (Grok Bot agents) during the event, which helped plan, write and test the code and docs. Gemma 4 is also used at run time to analyse messages.

## Limits

This is a helper, not a guarantee. A GREEN result means no known warning signs were found. If money is lost, call **1930** immediately and report at [cybercrime.gov.in](https://cybercrime.gov.in).

## License

Apache License 2.0. See [LICENSE](LICENSE).
