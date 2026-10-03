#!/usr/bin/env bash
# Rebuild /workspace/vercel_build/ : a deployable copy for Vercel (Python runtime + static public/). Does not deploy anything.
#   cd /workspace/vercel_build && vercel deploy --prod --token "$VERCEL_TOKEN"
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-/workspace/vercel_build}"

# keep the `vercel link` state (.vercel/) and its .gitignore across rebuilds
KEEP="$(mktemp -d)"
for k in .vercel .gitignore; do [ -e "$OUT/$k" ] && cp -a "$OUT/$k" "$KEEP/" || true; done
rm -rf "$OUT"
mkdir -p "$OUT/api" "$OUT/public"
for k in .vercel .gitignore; do [ -e "$KEEP/$k" ] && cp -a "$KEEP/$k" "$OUT/" || true; done
rm -rf "$KEEP"
cd "$ROOT"

# --- backend (the app module is renamed thagi_app.py so Vercel's FastAPI auto-detection of a root app.py
#     doesn't compete with api/index.py; ROOT-relative paths inside it still resolve to the bundle root) ---
cp app.py "$OUT/thagi_app.py"
for f in auth.py checks.py complaint.py llm.py; do cp "$f" "$OUT"/; done

# --- data the function reads at runtime (single source of truth: served by the function, not duplicated in public/) ---
cp -r samples "$OUT"/
mkdir -p "$OUT/sample_cache/complaints"
# allowlist: ONLY the cache entries for the 5 samples x en/hi/gu (same key as app._cache_path), never stray local entries
python3 - "$ROOT" "$OUT" <<'PY'
import hashlib, pathlib, shutil, sys
root, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
n = 0
for png in sorted((root / "samples").glob("*.png")):
    txt = png.with_suffix(".txt")
    if not txt.is_file():
        continue
    norm = " ".join(txt.read_text(encoding="utf-8").split())
    for lang in ("en", "hi", "gu"):
        h = hashlib.sha256(png.read_bytes() + b"\0" + norm.encode() + b"\0" + lang.encode()).hexdigest() + ".json"
        src = root / "sample_cache" / h
        if src.is_file():
            shutil.copy2(src, out / "sample_cache" / h); n += 1
if (root / "sample_cache" / "complaints").is_dir():
    for f in (root / "sample_cache" / "complaints").glob("*.json"):
        shutil.copy2(f, out / "sample_cache" / "complaints" / f.name)
print(f"sample_cache allowlist: {n} sample entries copied")
PY

# --- static frontend: public/ is served by Vercel's CDN at / ---
cp -r web/. "$OUT/public/"

cat > "$OUT/api/index.py" <<'EOF'
"""Vercel entrypoint: expose the FastAPI app. All paths in the app are relative to its own file (project root)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thagi_app import app  # noqa: E402,F401
EOF

# lean runtime deps (no pytest / uvicorn)
cat > "$OUT/requirements.txt" <<'EOF'
fastapi>=0.110
python-multipart>=0.0.9
google-genai>=2.0
httpx>=0.27
google-auth>=2.20
requests>=2.28
pillow>=10.0
EOF

echo "3.13" > "$OUT/.python-version"

cat > "$OUT/vercel.json" <<'EOF'
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "api/index.py": {
      "maxDuration": 60,
      "includeFiles": "{sample_cache,samples}/**"
    }
  }
}
EOF

cat > "$OUT/.vercelignore" <<'EOF'
__pycache__
*.pyc
.env
.env.*
EOF

find "$OUT" -name '__pycache__' -type d -prune -exec rm -rf {} +
rm -f "$OUT/.env"

echo "Built $OUT"
( cd "$OUT" && find . -not -path './sample_cache/*' -not -path './samples/*' -not -path './public/*' | sort
  echo "public: $(ls public | tr '\n' ' ')"
  echo "samples: $(ls samples | wc -l) files; sample_cache: $(ls sample_cache/*.json | wc -l) + $(ls sample_cache/complaints/*.json 2>/dev/null | wc -l) complaints"
  echo "project files size: $(du -sh . | cut -f1)" )
