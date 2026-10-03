# STATUS - Thagi Pakdo (manager: Build Manager)
Start 12:30 PM IST. Demo-ready target 2:00 PM IST. All times IST.
Rule: after each task, ping Build Manager with files changed + how you tested; wait for approve/fixes.

## Blockers (user must provide)
- GEMINI_API_KEY (env var on box) - needed for first real Gemma run
- gh login (GitHub account) - needed to create the public repo (QA, by ~1:30)

## Tasks
| # | Owner | Task | Target | State |
|---|-------|------|--------|-------|
| B1 | Backend | checks.py + tests/test_checks.py (URLs, UPI, phones, amounts, shorteners, punycode, TLDs, urgency/KYC/OTP/collect/prize, severity score) ; requirements.txt | 12:50 | APPROVED |
| B2 | Backend | llm.py (gemini, JSON parse, local fallback, failover) + app.py POST /api/check + static serving web/ + sample_cache | 1:15 | APPROVED (needs /samples mount) |
| B3 | Backend | /api/samples endpoint + cache of 5 sample results; full e2e on 5 samples (en + gu/hi) | 1:30 | assigned |
| F1 | Frontend | web/index.html+app.js+style.css: input, drag/paste image, lang buttons, verdict card (mock JSON), 4+ sample buttons | 12:55 | APPROVED |
| F2 | Frontend | Wire to /api/check, Read-aloud (hide if no voice), privacy note, loading/error states | 1:20 | review fixes |
| F3 | Frontend | samples/ PNG screenshots (5, fake only) matching QA's .txt | 12:50 | APPROVED |
| Q1 | QA | LICENSE (Apache-2.0), .gitignore, samples/*.txt (5), git init | 12:45 | APPROVED |
| Q2 | QA | skills/scam-check/SKILL.md + scripts/check.py, validate | 1:15 | assigned |
| Q3 | QA | README (run steps, license, AI assistants credit, originality), demo script, create public repo + commits | 1:30 | queued |
| Q4 | QA | final e2e test of Definition of Done | 1:45 | queued |

## Milestones
1. first end-to-end run - 12:35 code-only path OK (no Gemini key yet)
2. all tasks approved - not yet
3. demo-ready (2:00) - not yet

## Log
- 12:35 B1,B2,F1,F3,Q1 approved. Code-only path OK.
- 12:50 Live Gemma OK (image+text, en/hi/gu). Latency 20-60s uncached -> Backend fixing (thinking off, downscale, timeout, prewarm). Q2 approved.
- GitHub account: Neelk1812, repo thagi-pakdo; waiting on gh login (Judge arranging).
- 13:00 F4 mobile redesign approved, B4 /api/complaint approved (live on :8000). F5 complaint UI built, re-test vs real endpoint.
- 13:01 New: B5/F6 Google sign-in + BYOK Gemini key, OFF unless GOOGLE_CLIENT_ID set. Need client ID from user.
- Public tunnel not possible from box (egress blocked). APK deferred; needs hosting + OAuth.
- Freeze 13:40 for demo path; QA then commits all (web icons, docs/screens, complaint.py, sample_cache/complaints) and re-runs clean clone.
