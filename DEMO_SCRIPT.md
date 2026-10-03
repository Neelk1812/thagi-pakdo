# Thagi Pakdo - 2-minute live demo script

Everything uses **fake samples only**. Status of items marked [unverified]: not yet rehearsed end to end; Gemini key and live Gemma run were pending when this was drafted.

**Before going on stage (checklist)**
- `uvicorn app:app` running; page open at http://127.0.0.1:8000 in a full-screen browser, language = English.
- `GEMINI_API_KEY` set **[unverified]**; every sample already run once so `sample_cache/` makes them instant even if Wi-Fi or rate limits fail.
- Browser has a Gujarati/Hindi voice for Read-aloud **[unverified on the demo laptop]**; test the speaker volume.
- Optional: local Gemma server (Ollama) up as backup **[unverified]**.
- Sample screenshots ready: `samples/courier_fee.png`.

| Time | What you do | What you say |
|---|---|---|
| 0:00-0:15 | Title slide / the page open. | "Every week people in Gujarat lose money to a fake KYC SMS, a UPI 'refund', or a 'parcel fee' message. Many can't tell, and many find English hard. Thagi Pakdo - catch the con - tells you in your language if a message is a scam." |
| 0:15-0:40 | Click **Try sample: Fake KYC SMS** (or paste `samples/kyc_sms.txt`). Click Check. Red card appears. | "This SMS says our SBI account will be blocked, with a short link. Red, with reasons: shortened link, urgency, bank KYC over SMS. And it says what to do: don't click, block it, call 1930." |
| 0:40-1:00 | Drag `samples/courier_fee.png` onto the page (or click the courier sample), Check. | "Most scams arrive as WhatsApp screenshots. Upload the screenshot and Gemma reads it. Fake India Post fee, fake .xyz link - red." |
| 1:00-1:20 | Press **ગુજરાતી**, then **हिन्दी**; the card re-renders. | "Same verdict in Gujarati and Hindi, so grandparents can understand it." (If the card does not translate instantly, re-click Check; the cached result is fast.) |
| 1:20-1:35 | Press **Read aloud**. Let 5-8 seconds play, then stop. | "And it can read the answer out loud for anyone who can't read well." (If no voice is installed the button is hidden by design - say so and skip.) |
| 1:35-1:50 | Click **Try sample: safe bank OTP**. Green card. | "It isn't paranoid: a genuine bank OTP alert with no link and no ask is green. The rule is simple: our plain code can raise the alarm, but the AI can never lower it." |
| 1:50-2:00 | Wrap-up, show privacy note / repo. | "If Gemini is rate-limited or offline it falls back to local Gemma 4 E4B, so real messages can stay on your phone or laptop. Open source, Apache-2.0, an Agent Skill included. Thagi Pakdo - thank you." |

**Backup moves**
- If the network or Gemini fails: samples are cached, so they still respond; the card shows a "Cached" / "Rules only" badge. Say: "It still works offline - that's the failover."
- If local fallback is asked about: say it is configured with `LLM_BACKEND=local` and tested by unit tests; the live Gemma E4B run is **[unverified]** unless proven before the demo.
- If a Gujarati/Hindi translation looks off, say the AI writes it fresh for every check and move on.

**Likely judge questions**
- *Why not just use an LLM?* Plain-code checks are fast, explainable and never hallucinate a green on an obvious scam.
- *Privacy?* Free Gemini tier may use inputs; demo uses fake samples; real messages -> local mode.
- *What's original?* See README, "What's original".
