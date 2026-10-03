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

Requires Python 3.13 (older 3.10+ should also work **[unverified]**).

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your-key      # optional: without it, rules-only / local fallback is used
uvicorn app:app
```

Open http://127.0.0.1:8000. Check http://127.0.0.1:8000/api/health to see which backend is configured.

### Configuration (environment variables / `.env`)

Copy `.env.example` to `.env` and fill it in (`.env` is git-ignored; never commit keys). `app.py` does **not** load `.env` by itself (no python-dotenv); it reads real environment variables. Load it into your shell first (Linux/macOS: `set -a; source .env; set +a; uvicorn app:app`), or export the variables yourself. (`uvicorn --env-file .env` only works if you also `pip install python-dotenv`, which is not in `requirements.txt`.)

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

Local mode is selected with `LLM_BACKEND=local`. It has **not yet been tested with a real Gemma 4 E4B server [unverified]**; the failover code is covered by unit tests only.

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
