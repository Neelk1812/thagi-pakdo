#!/usr/bin/env python3
"""Fill sample_cache/ by running every samples/<name>.png + <name>.txt in en/hi/gu through /api/check.
Usage: python scripts/prewarm.py [--url http://localhost:8000/api/check | --inproc] [--langs en,hi,gu]
Exit 1 if any result is ai_unavailable (not cached) or any request fails; exit 2 if samples are missing."""
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000/api/check")
    ap.add_argument("--inproc", action="store_true", help="call the app in-process (needs GEMINI_API_KEY in env)")
    ap.add_argument("--langs", default="en,hi,gu")
    ap.add_argument("--expect", type=int, default=5)
    a = ap.parse_args()
    langs = [x.strip() for x in a.langs.split(",") if x.strip()]

    txts = {p.stem for p in SAMPLES.glob("*.txt")}
    pngs = {p.stem for p in SAMPLES.glob("*.png")}
    ready = sorted(txts & pngs)
    for n in sorted(txts - pngs): print(f"MISSING png: samples/{n}.png")
    for n in sorted(pngs - txts): print(f"MISSING txt: samples/{n}.txt")
    if len(ready) < a.expect: print(f"WARNING: {len(ready)} complete samples, expected {a.expect}")
    if not ready:
        print("No samples to run."); return 2

    if a.inproc:
        sys.path.insert(0, str(ROOT))
        from fastapi.testclient import TestClient
        import app as appmod
        client = TestClient(appmod.app); post = lambda **kw: client.post("/api/check", **kw)
    else:
        import httpx
        post = lambda **kw: httpx.post(a.url, timeout=180, **kw)

    rows, bad = [], 0
    for n in ready:
        img = (SAMPLES / f"{n}.png").read_bytes()
        text = (SAMPLES / f"{n}.txt").read_text(encoding="utf-8").strip()
        for lang in langs:
            try:
                r = post(files={"image": (f"{n}.png", img, "image/png")}, data={"text": text, "lang": lang})
                r.raise_for_status(); j = r.json()
                ok = not j.get("ai_unavailable")
                rows.append((n, lang, j.get("verdict"), j.get("source"), "ok" if ok else "AI_UNAVAILABLE"))
            except Exception as e:
                ok = False; rows.append((n, lang, "-", "-", f"ERROR {type(e).__name__}: {str(e)[:80]}"))
            bad += (not ok)
    print(f"{'sample':<14}{'lang':<6}{'verdict':<9}{'source':<9}status")
    for r in rows: print(f"{r[0]:<14}{r[1]:<6}{str(r[2]):<9}{str(r[3]):<9}{r[4]}")
    print(f"\n{len(rows) - bad}/{len(rows)} cached OK" + (f", {bad} FAILED (ai unavailable/errors; not cached)" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
