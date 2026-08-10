"""Score the hard-negative benign fixtures (scripts/fetch_hard_negatives.py)
through the REAL page_extractor.js (via Node) and the current, unmodified
trained model -- no retraining here, this is a pure evaluation pass.

Writes:
- data/evaluation/hard_negatives_manifest.jsonl -- one row per URL,
  included/excluded status + reason, and the extracted feature vector
  for included rows (never raw HTML -- small, safe to commit).
- data/evaluation/hard_negatives_scored.json -- classifier/judge/fused
  scores for every included row.

Usage:
    python scripts/fetch_hard_negatives.py   # first, to populate fixtures
    python scripts/eval_hard_negatives.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests_js" / "hard_negative_fixtures"
JS_RUNNER = REPO_ROOT / "tests_js" / "extract_features.mjs"
FETCH_LOG = REPO_ROOT / "data" / "evaluation" / "hard_negatives_fetch_log.txt"
MANIFEST_OUT = REPO_ROOT / "data" / "evaluation" / "hard_negatives_manifest.jsonl"
SCORED_OUT = REPO_ROOT / "data" / "evaluation" / "hard_negatives_scored.json"

EXCLUDE_TRIVIAL_BYTES = 200  # e.g. a bare redirect-stub page

sys.path.insert(0, str(REPO_ROOT / "src"))


def build_manifest() -> list[dict]:
    node = shutil.which("node")
    if node is None:
        raise SystemExit("node not found on PATH -- see LOCAL_SETUP.md for how to install it")

    entries = []
    with open(FETCH_LOG) as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            if len(parts) != 4:
                continue
            name, url, size, note = parts
            entries.append((name, url, int(size), note))

    manifest = []
    for name, url, size, note in entries:
        fpath = FIXTURES / f"{name}.html"
        if note != "ok" or not fpath.exists() or size < EXCLUDE_TRIVIAL_BYTES:
            reason = note if note != "ok" else "trivial/stub content"
            manifest.append({"name": name, "url": url, "size": size, "status": "excluded", "reason": reason})
            continue

        result = subprocess.run(
            [node, str(JS_RUNNER), str(fpath), url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            manifest.append(
                {"name": name, "url": url, "size": size, "status": "excluded",
                 "reason": f"js extract failed: {result.stderr[:200]}"}
            )
            continue
        features = json.loads(result.stdout)
        manifest.append({"name": name, "url": url, "size": size, "status": "included", "features": features})

    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_OUT, "w") as f:
        for row in manifest:
            f.write(json.dumps(row) + "\n")
    return manifest


def score_manifest(manifest: list[dict]) -> list[dict]:
    import joblib

    from phishshield.judge.judge import judge_features, risk_band
    from phishshield.models.classifier import predict_feature_dict

    model = joblib.load(REPO_ROOT / "artifacts" / "phishing_classifier.joblib")
    FUSION_ALPHA = 0.7

    rows = []
    for d in manifest:
        if d["status"] != "included":
            continue
        feats = dict(d["features"])
        feats.pop("_meta_url", None)
        feats.pop("_meta_title", None)
        classifier_score = predict_feature_dict(model, feats)
        verdict = judge_features(feats)
        judge_score = verdict.risk_score / 100
        fused = FUSION_ALPHA * classifier_score + (1 - FUSION_ALPHA) * judge_score
        risk_score = round(fused * 100)
        rows.append({
            "name": d["name"], "url": d["url"], "has_html": feats.get("has_html"),
            "classifier_score": classifier_score, "judge_score": judge_score,
            "risk_score": risk_score, "risk_band": risk_band(risk_score),
        })

    with open(SCORED_OUT, "w") as f:
        json.dump(rows, f, indent=2)
    return rows


def report(rows: list[dict]) -> None:
    n = len(rows)
    scores = sorted(r["risk_score"] for r in rows)

    def pct(p: float) -> int:
        return scores[min(n - 1, int(len(scores) * p))]

    fpr = sum(1 for s in scores if s >= 50) / n
    print(f"n = {n}")
    print(f"FPR (risk_score >= 50): {fpr:.1%}")
    print(f"mean: {sum(scores) / n:.1f}  median: {pct(0.5)}  p75: {pct(0.75)}  p90: {pct(0.9)}  p95: {pct(0.95)}  max: {scores[-1]}")
    for t in (40, 50, 70, 80):
        print(f"  >= {t}: {sum(1 for s in scores if s >= t) / n:.1%}")
    print(f"\nBand distribution: {Counter(r['risk_band'] for r in rows)}")
    print("\nWorst 10:")
    for r in sorted(rows, key=lambda r: -r["risk_score"])[:10]:
        print(
            f"  {r['name']:<20} {r['url']:<55} risk={r['risk_score']:>3} ({r['risk_band']:>6})"
            f"  classifier={r['classifier_score']:.3f} judge={r['judge_score']:.2f}"
        )


def main() -> None:
    manifest = build_manifest()
    included = [m for m in manifest if m["status"] == "included"]
    excluded = [m for m in manifest if m["status"] == "excluded"]
    print(f"Included: {len(included)}, Excluded: {len(excluded)}")
    print("Excluded (and why):")
    for m in excluded:
        print(f"  {m['name']}: {m['reason']}")
    print()

    rows = score_manifest(manifest)
    report(rows)


if __name__ == "__main__":
    main()
