"""CLI entry point for the Phase 4 mitigation experiment: fold a fraction of
the LLM-generated partition into training, compare before/after, and ablate
classifier-only vs. classifier+judge fusion.

Usage:
    python -m phishshield.models.run_mitigation \\
        --phishtank data/raw/verified_online.csv \\
        --openphish data/raw/openphish_feed.txt \\
        --tranco data/raw/tranco_top1m.csv \\
        --llm-generated data/generated/llm_phishing_v1.jsonl

Requires the same local dataset snapshots as
`phishshield.models.train_baseline` (no network/LLM calls here either).
"""

from __future__ import annotations

import argparse

from phishshield.data.loaders import load_llm_generated, load_openphish, load_phishtank, load_tranco
from phishshield.models.mitigation import run_mitigation_experiment
from phishshield.models.report import plot_grouped_metric

DEFAULT_BEFORE_AFTER_CSV = "reports/phase4_before_after.csv"
DEFAULT_ABLATION_CSV = "reports/phase4_ablation.csv"
DEFAULT_BEFORE_AFTER_PLOT = "reports/phase4_before_after_recall.png"
DEFAULT_ABLATION_PLOT = "reports/phase4_ablation_recall.png"
DEFAULT_JUDGE_LOG = "reports/phase4_judge_log.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phishtank", required=True)
    parser.add_argument("--openphish", required=True)
    parser.add_argument("--tranco", required=True)
    parser.add_argument("--tranco-limit", type=int, default=5000)
    parser.add_argument("--llm-generated", required=True)
    parser.add_argument("--fold-fraction", type=float, default=0.5)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--alpha", type=float, default=0.5, help="classifier weight in fusion")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--judge-log", default=DEFAULT_JUDGE_LOG, help="path to write the judge's evaluation log (JSONL); pass '' to skip")
    args = parser.parse_args()

    legacy_samples = (
        load_phishtank(args.phishtank)
        + load_openphish(args.openphish)
        + load_tranco(args.tranco, limit=args.tranco_limit)
    )
    llm_samples = load_llm_generated(args.llm_generated)

    result = run_mitigation_experiment(
        legacy_samples,
        llm_samples,
        fold_fraction=args.fold_fraction,
        test_size=args.test_size,
        seed=args.seed,
        alpha=args.alpha,
        judge_log_path=args.judge_log or None,
    )

    print("=== before/after retraining ===")
    print(result.before_after.to_string(index=False))
    print("\n=== classifier-only vs. classifier+judge ablation ===")
    print(result.ablation.to_string(index=False))

    result.before_after.to_csv(DEFAULT_BEFORE_AFTER_CSV, index=False)
    result.ablation.to_csv(DEFAULT_ABLATION_CSV, index=False)

    plot_grouped_metric(
        result.before_after, x_col="partition", hue_col="model", metric="recall",
        out_path=DEFAULT_BEFORE_AFTER_PLOT,
        title="Recall before vs. after folding in LLM-generated samples",
    )
    plot_grouped_metric(
        result.ablation, x_col="partition", hue_col="variant", metric="recall",
        out_path=DEFAULT_ABLATION_PLOT,
        title="Recall: classifier-only vs. classifier+judge fusion",
    )
    written = [DEFAULT_BEFORE_AFTER_CSV, DEFAULT_ABLATION_CSV, DEFAULT_BEFORE_AFTER_PLOT, DEFAULT_ABLATION_PLOT]
    if args.judge_log:
        written.append(args.judge_log)
    print(f"\nwrote {', '.join(written)}")


if __name__ == "__main__":
    main()
