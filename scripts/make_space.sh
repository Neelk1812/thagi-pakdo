#!/usr/bin/env bash
# Rebuild /workspace/space_build/ : a deployable copy for a Hugging Face Space (Docker SDK). Does not deploy anything.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-/workspace/space_build}"

rm -rf "$OUT"
mkdir -p "$OUT"
cd "$ROOT"

cp Dockerfile .dockerignore requirements.txt LICENSE "$OUT"/
for f in app.py auth.py checks.py complaint.py llm.py; do cp "$f" "$OUT"/; done
for d in web samples sample_cache skills; do cp -r "$d" "$OUT"/; done
mkdir -p "$OUT/sample_cache/complaints"
find "$OUT" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$OUT" -name '*.pyc' -delete
rm -f "$OUT/.env"

cat > "$OUT/README.md" <<'EOF'
---
title: Thagi Pakdo
emoji: 🛡️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# Thagi Pakdo (ઠગી પકડો)

A free scam checker for ordinary people in India: paste a message or upload a screenshot of an SMS, WhatsApp chat, UPI request or email and get a clear red / amber / green verdict with simple reasons, in English, Hindi or Gujarati. It can also draft a complaint for the National Cybercrime Reporting Portal (helpline 1930).

**Privacy note:** this is a free-tier demo. Inputs sent to the AI model may be used by Google to improve its products, so please try only the built-in fake samples or made-up messages here. Never paste real OTPs, card numbers or personal details.

See the GitHub repo for the source, setup and how to run it locally (including a fully offline mode).
EOF

echo "Built $OUT"
( cd "$OUT" && find . -not -path './sample_cache/*' -not -path './web/*' -not -path './samples/*' -not -path './skills/*' | sort; echo "web: $(ls web | wc -l) files, samples: $(ls samples | wc -l), sample_cache: $(ls sample_cache/*.json | wc -l) + $(ls sample_cache/complaints/*.json 2>/dev/null | wc -l) complaints, skills: $(find skills -type f | wc -l) files" )
