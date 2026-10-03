#!/usr/bin/env python3
"""Offline scam check for a suspicious message. Prints JSON.

Usage:
    python scripts/check.py "message text"
    python scripts/check.py --file message.txt
    echo "message text" | python scripts/check.py

Uses the plain-code rules in the repo-root checks.py (no network, no LLM).
Exit code: 0 = green, 1 = amber, 2 = red, 64 = usage/setup error.
"""
import json
import sys
from pathlib import Path

# scripts/ -> scam-check/ -> skills/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

try:
    from checks import analyze  # analyze(text) -> {score, severity, flags, strong, extracted}
except ImportError as e:
    print(json.dumps({"error": f"cannot import checks.py from {REPO_ROOT}: {e}"}))
    sys.exit(64)

ADVICE = {
    "red": [
        "Do not pay anything and do not click any link.",
        "Never share your OTP, UPI PIN, CVV or passwords. Do not approve any UPI collect request.",
        "Block the sender and delete the message.",
        "If you already lost money or shared details, call the cybercrime helpline 1930 right away and report at https://cybercrime.gov.in.",
    ],
    "amber": [
        "Do not click links or pay until you have verified the sender.",
        "Contact the bank/company only via its official app, website or the number on your card.",
        "If it turns out to be a scam, block the sender and report at 1930 / https://cybercrime.gov.in.",
    ],
    "green": [
        "No scam signs found by the offline rules, but stay careful.",
        "Never share the OTP with anyone, even if they say they are from the bank.",
    ],
}


def main(argv):
    args = argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args and args[0] == "--file":
        if len(args) < 2:
            print(json.dumps({"error": "--file needs a path"}))
            return 64
        text = Path(args[1]).read_text(encoding="utf-8")
    elif args:
        text = " ".join(args)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print(json.dumps({"error": "no message given; pass text as an argument or via stdin"}))
        return 64
    if not text.strip():
        print(json.dumps({"error": "empty message"}))
        return 64

    res = analyze(text)
    verdict = res["severity"]
    out = {
        "verdict": verdict,
        "score": res["score"],
        "reasons": res["flags"],
        "extracted": res["extracted"],
        "advice": ADVICE[verdict],
        "note": "Offline rule-based check only (no AI). Absence of flags is not proof a message is safe.",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return {"green": 0, "amber": 1, "red": 2}[verdict]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
