# Thagi Pakdo - 2-minute live demo script

Everything uses **fake samples only**. Screenshots of the final look are in `docs/screens/v2/` (e.g. `f7b_scam_light_390.png`). Tested from a clean clone on 3 Oct 2026: all 5 samples give the right verdict in en/hi/gu, the complaint draft works, and the page fits a 390 px phone screen. Items marked **[unverified]** have not been tried.

**Before going on stage (checklist)**
- `uvicorn app:app` running; page open at http://127.0.0.1:8000 full screen, language = English. (Phone demo: `uvicorn app:app --host 0.0.0.0` and open `http://<laptop-ip>:8000` on the same Wi-Fi **[unverified on the demo network]**.)
- `GEMINI_API_KEY` in `.env`. The **Try-sample buttons** hit `sample_cache/` and answer in about 10 ms, even with no Wi-Fi or a rate limit. Anything new (your own pasted text or screenshot) is a live call, about 2 to 4 s (screenshots up to about 5 s), and the complaint draft takes about 8 s, so keep talking while the spinner runs.
- Do a dry run of your **live paste** text once beforehand so that, if the network dies on stage, it is cached. Suggested text: `Dear Customer, your ICICI account will be BLOCKED today due to pending KYC. Update now: http://bit.ly/icici-kyc-55` (all fake).
- Browser has a Gujarati/Hindi voice for Read-aloud **[unverified on the demo laptop]**; test the volume. The button hides itself if there is no voice.
- **Backup if the laptop or Wi-Fi misbehaves:** the live copy at https://thagi-pakdo.vercel.app (open it in a second tab before you start). It uses a shared free-tier Gemini key, so a new paste may be slow or rate limited (about 2.5 to 8 s normally), but the 5 sample buttons are instant from cache. Its availability on the day is **[unverified until you open it]**.
- Google sign-in is **off** by default; do not set `GOOGLE_CLIENT_ID` for the demo.
- Optional backup: local Gemma server (Ollama) with `LLM_BACKEND=local` **[unverified with a real Gemma E4B]**.

| Time | What you do | What you say |
|---|---|---|
| 0:00-0:15 | Page open on the home screen. | "Every week people in Gujarat lose money to a fake KYC SMS, a UPI 'refund' or a 'parcel fee' message, and many find English hard. Thagi Pakdo - catch the con - tells you in your language if a message is a scam." |
| 0:15-0:35 | Tap **Fake KYC SMS**, then **Courier fee WhatsApp** (the sample buttons). A red card appears instantly: a SCAM tag and the sentence "This looks like a scam. Do not pay or click." | "One tap, no typing. This SBI KYC SMS is red: shortened link, urgency, banks never do KYC by SMS. The courier one is a WhatsApp *screenshot* - Gemma reads the image - fake India Post fee, fake .xyz link." |
| 0:35-1:00 | Clear the form, **paste your fresh text** (or a new message from a judge, fake only), press **Check**. Wait 2-4 s. | "Now a message the system has never seen. Plain-code rules and Gemma both check it live, and the stricter answer wins, so the AI can never lower a red flag." |
| 1:00-1:30 | Tap **Draft a complaint**, fill only the name and "what happened" (or leave blank), press Generate. Show the `[placeholders]`. | "One more step people struggle with: reporting. It drafts the cybercrime-portal complaint. It never invents facts: anything we don't know stays a visible placeholder. They copy it and file at cybercrime.gov.in or call 1930." (Live draft takes about 8 s; the sample's cached draft is instant.) |
| 1:30-1:45 | Press **ગુજરાતી**, then **हिन्दी**. The card re-renders. Press **Read aloud** for 5 s, then stop. | "Same answer in Gujarati and Hindi, and it can read it out loud for anyone who can't read well." (If the card is slow after a switch, wait a few seconds - non-sample text is a new live call. If no voice is installed, skip read-aloud.) |
| 1:45-1:55 | Tap **Safe bank OTP**. Green card: "This looks safe, but stay alert." | "It isn't paranoid: a genuine OTP alert with no link and no ask is green." |
| 1:55-2:00 | Wrap-up, show the repo and the **Privacy** link at the top of the page. | "If Gemini is rate-limited or offline it falls back to a local Gemma, then to plain rules, so real messages can stay on your own machine. Open source, Apache-2.0, with an Agent Skill. Thagi Pakdo - thank you." |

**Backup moves**
- Network or Gemini fails: sample buttons still work from cache; a new paste shows a "Rules only" / "AI unavailable" note with a red/amber/green from the rules. Say: "That is the failover - it still protects you."
- Local fallback question: `LLM_BACKEND=local` points the app at a local OpenAI-compatible server; failover was tested with a stub server, but a real Gemma E4B run is **[unverified]**.
- If a Gujarati/Hindi sentence reads oddly: the AI writes it fresh for every check; move on.
- If the complaint draft is slow: say "the AI is writing a formal letter" and continue; there is an offline template if the AI is down.

**Likely judge questions**
- *Why not just use an LLM?* Plain-code checks are fast, explainable and can't hallucinate a green on an obvious scam; the LLM adds screenshot reading and explanations.
- *Privacy?* Free Gemini tier may use inputs; the demo uses fake samples; real messages -> `LLM_BACKEND=local`. Complaint details you type are not cached or logged.
- *Sign-in?* Optional and off by default; a host can enable Google sign-in so each user brings their own Gemini key (see AUTH.md). **[Google sign-in with a real account is unverified.]**
- *What's original?* See the README "What's original" section.
