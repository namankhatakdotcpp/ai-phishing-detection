"""CLI entry point for the Phase 3 experiment: train the baseline classifier
on legacy data only, evaluate it on held-out legacy data vs. the
LLM-generated partition, and save the headline comparison table + plot.

Usage:
    python -m phishshield.models.train_baseline \\
        --phishtank data/raw/verified_online.csv \\
        --openphish data/raw/openphish_feed.txt \\
        --tranco data/raw/tranco_top1m.csv \\
        --llm-generated data/generated/llm_phishing_v1.jsonl

Requires the raw dataset snapshots to already be downloaded into
`data/raw/` and the LLM-generated partition to already be produced via
`phishshield.data.generate_llm_dataset` (see PROJECT_BRIEF.md, Phase 2/3;
this script makes no network or LLM calls itself).
"""

from __future__ import annotations

import argparse

from phishshield.data.loaders import load_llm_generated, load_openphish, load_phishtank, load_tranco
from phishshield.data.pipeline import build_feature_dataframe
from phishshield.data.splits import build_partitions
from phishshield.models.classifier import train_classifier
from phishshield.models.evaluate import compare_partitions
from phishshield.models.report import plot_partition_comparison

DEFAULT_REPORT_CSV = "reports/phase3_legacy_vs_llm.csv"
DEFAULT_REPORT_PLOT = "reports/phase3_legacy_vs_llm.png"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phishtank", required=True)
    parser.add_argument("--openphish", required=True)
    parser.add_argument("--tranco", required=True)
    parser.add_argument("--tranco-limit", type=int, default=5000)
    parser.add_argument("--llm-generated", required=True)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--report-csv", default=DEFAULT_REPORT_CSV)
    parser.add_argument("--report-plot", default=DEFAULT_REPORT_PLOT)
    args = parser.parse_args()

    legacy_samples = (
        load_phishtank(args.phishtank)
        + load_openphish(args.openphish)
        + load_tranco(args.tranco, limit=args.tranco_limit)
    )
    llm_samples = load_llm_generated(args.llm_generated)

    partitions = build_partitions(
        legacy_samples, llm_samples, test_size=args.test_size, seed=args.seed
    )

    train_df = build_feature_dataframe(partitions.train)
    legacy_test_df = build_feature_dataframe(partitions.legacy_test)
    llm_holdout_df = build_feature_dataframe(partitions.llm_holdout)

    model = train_classifier(train_df)

    comparison = compare_partitions(
        model,
        {"legacy_test": legacy_test_df, "llm_generated_holdout": llm_holdout_df},
    )
    print(comparison.to_string(index=False))

    comparison.to_csv(args.report_csv, index=False)
    plot_partition_comparison(comparison, args.report_plot)
    print(f"wrote {args.report_csv} and {args.report_plot}")


if __name__ == "__main__":
    main()
