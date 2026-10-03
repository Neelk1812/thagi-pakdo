---
name: scam-check
description: Checks a suspicious SMS, WhatsApp, UPI or email message for scam signs (fake KYC, UPI collect requests, courier fees, lottery or prize bait, OTP theft, lookalike links) in an India context, with Gujarati, Hindi and English support. Use when a user pastes or describes a message and asks "is this a scam?", or wants safe next steps and where to report it.
license: Apache-2.0
compatibility: Requires Python 3 and the Thagi Pakdo repo (the script imports checks.py from the repo root). Works offline; no API key needed.
metadata:
  project: thagi-pakdo
  region: IN
  languages: "gu hi en"
---

# Scam check (India)

Use this skill to judge whether a message is likely a scam and to tell the user what to do next. It targets common Indian fraud patterns: fake bank KYC SMS with short links, UPI "refund" collect requests, fake courier/India Post fee messages, KBC/lottery prizes, and anyone asking for an OTP or UPI PIN.

## When to use

- The user pastes or describes an SMS, WhatsApp, UPI request or email and asks if it is safe.
- The user is about to click a link, pay a fee, approve a UPI request or share an OTP.
- The user asks where to report fraud in India.

## How to use

1. Get the message text. For a screenshot, read the text off the image first.
2. Run the offline checker from the skill directory (or give the full path):

   ```bash
   python scripts/check.py "Dear Customer, your SBI account will be BLOCKED today. Update KYC: http://bit.ly/abc"
   python scripts/check.py --file message.txt
   echo "message text" | python scripts/check.py
   ```

   The script imports `analyze` from `checks.py` in the repo root, so run it inside a checkout of the repo.
3. Read the JSON, then explain the result in the user's language (Gujarati, Hindi or English), in 2 to 4 plain reasons plus the advice below.
4. Combine with your own judgment. The script is rule-based only. A `green` result means no known red flags were found, not that the message is proven safe. Never downgrade a `red` result.

## Output

The script prints one JSON object:

```json
{
  "verdict": "red",
  "score": 100,
  "reasons": ["URL shortener hides the real link (bit.ly)", "KYC update with a link (classic bank-KYC scam)"],
  "extracted": {"urls": [], "phones": [], "upi_ids": [], "amounts": []},
  "advice": ["Do not pay anything and do not click any link.", "..."],
  "note": "Offline rule-based check only (no AI). ..."
}
```

- `verdict`: `red` (almost certainly a scam), `amber` (suspicious, verify first), `green` (no red flags found).
- `score`: 0 to 100 from the rule hits.
- Exit code: 0 green, 1 amber, 2 red, 64 usage error.

## What to tell the user

For `red` or `amber`:

- Do not pay, do not click the link, do not call back numbers in the message.
- Never share an OTP, UPI PIN, CVV or password. You never need a PIN to receive money; approving a collect request sends money out.
- Block the sender and delete the message.
- Verify only through the official app, website or the number printed on your card.
- If money was lost or details were shared: call the national cybercrime helpline **1930** immediately (faster is better for freezing funds), report at **https://cybercrime.gov.in**, and tell your bank to block the card or account.

For `green`: say no scam signs were found, but remind the user that banks never ask for OTP or PIN.

## Notes

- Only use fake or consented messages when demonstrating. Do not send real personal messages to third-party services.
- Sample inputs live in `samples/*.txt` at the repo root.
