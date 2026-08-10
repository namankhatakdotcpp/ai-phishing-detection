"""CLI entry point: train the classifier on the full real dataset (real
PhishTank/OpenPhish/Tranco + fetched benign HTML + real LLM-generated
partition) and serialize it to a committed artifact the demo API loads at
startup, replacing the toy `build_synthetic_legacy_pool()` model that was
found to give backwards verdicts on realistic inputs (see
PROJECT_BRIEF.md, Phase 6 Sprint 1 entry).

Trains on the FULL dataset (no train/test split) to maximize the
deployed model's real-world accuracy -- this script is not an evaluation
run. The report's held-out precision/recall/F1/FPR numbers come from
`build_report_assets`/`train_baseline`, which do split; nothing here
should be read as an eval result.

The serialized artifact contains only the fitted tree ensemble (numeric
split thresholds over the feature schema) -- not the training URLs/HTML
themselves -- so it's safe to commit even though the raw datasets it was
trained from are gitignored and not redistributed.

Usage:
    python -m phishshield.models.export_demo_model \\
        --phishtank data/raw/phishtank.csv \\
        --openphish data/raw/openphish.txt \\
        --tranco data/raw/tranco.csv --tranco-limit 5000 \\
        --tranco-html data/generated/tranco_benign_html.jsonl \\
        --llm-generated data/generated/llm_phishing_v1.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib

from phishshield.data.loaders import (
    load_llm_generated,
    load_openphish,
    load_phishtank,
    load_tranco,
    registrable_domain,
)
from phishshield.data.pipeline import build_feature_dataframe
from phishshield.models.classifier import train_classifier

DEFAULT_OUT = "artifacts/phishing_classifier.joblib"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phishtank", required=True)
    parser.add_argument("--openphish", required=True)
    parser.add_argument("--tranco", required=True)
    parser.add_argument("--tranco-limit", type=int, default=5000)
    parser.add_argument("--tranco-html", default=None, help="optional JSONL from fetch_tranco_html.py")
    parser.add_argument("--llm-generated", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    tranco_samples = load_tranco(args.tranco, limit=args.tranco_limit)
    if args.tranco_html:
        html_samples = load_llm_generated(args.tranco_html)
        # Match by registrable domain, not exact URL/hostname --
        # load_tranco() attaches a realistic (not necessarily matching)
        # subdomain/path per domain now.
        html_domains = {registrable_domain(s.url) for s in html_samples}
        tranco_samples = [
            s for s in tranco_samples if registrable_domain(s.url) not in html_domains
        ] + html_samples

    legacy_samples = load_phishtank(args.phishtank) + load_openphish(args.openphish) + tranco_samples
    llm_samples = load_llm_generated(args.llm_generated)
    all_samples = legacy_samples + llm_samples

    print(f"training on {len(all_samples)} samples ({len(legacy_samples)} legacy + {len(llm_samples)} llm)")
    train_df = build_feature_dataframe(all_samples)
    model = train_classifier(train_df)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_path)
    size_kb = out_path.stat().st_size / 1024
    print(f"wrote {out_path} ({size_kb:.1f} KiB)")


if __name__ == "__main__":
    main()
