"""CLI entry point for Phase 7: generate the report assets the course
writeup needs — dataset stats, the Phase 3 legacy-vs-LLM eval table, the
Phase 4 before/after + ablation tables, and two qualitative examples —
all into `reports/`.

By default this runs on `phishshield.data.synthetic`'s self-contained
synthetic legacy pool (no downloaded datasets required) plus the mocked
LLM-generated partition, and says so loudly in its output: those numbers
are illustrative, not the report's real headline result. Pass
--phishtank/--openphish/--tranco (all three together) to run on real
downloaded data instead — see PROJECT_BRIEF.md, Phase 1.

Usage (illustrative, no args needed):
    python -m phishshield.models.build_report_assets

Usage (real data):
    python -m phishshield.models.build_report_assets \\
        --phishtank data/raw/verified_online.csv \\
        --openphish data/raw/openphish_feed.txt \\
        --tranco data/raw/tranco_top1m.csv \\
        --llm-generated data/generated/llm_phishing_v1.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

from phishshield.data.generation import generate_llm_phishing_dataset
from phishshield.data.loaders import load_llm_generated, load_openphish, load_phishtank, load_tranco
from phishshield.data.pipeline import build_feature_dataframe
from phishshield.data.splits import build_partitions
from phishshield.data.stats import dataset_stats
from phishshield.data.synthetic import build_synthetic_legacy_pool
from phishshield.models.classifier import train_classifier
from phishshield.models.evaluate import compare_partitions
from phishshield.models.mitigation import run_mitigation_experiment
from phishshield.models.qualitative import find_legacy_catch_example, find_llm_flip_example
from phishshield.models.report import plot_grouped_metric, plot_partition_comparison

REPORTS_DIR = Path("reports")


def _load_legacy_samples(args: argparse.Namespace) -> tuple[list, str]:
    provided = [args.phishtank, args.openphish, args.tranco]
    if any(provided) and not all(provided):
        raise SystemExit("--phishtank/--openphish/--tranco must be provided together")

    if all(provided):
        tranco_samples = load_tranco(args.tranco, limit=args.tranco_limit)
        mode = "real"
        if args.tranco_html:
            html_samples = load_llm_generated(args.tranco_html)  # schema-generic loader
            html_urls = {s.url for s in html_samples}
            tranco_samples = [s for s in tranco_samples if s.url not in html_urls] + html_samples
            mode = f"real (+ {len(html_samples)} Tranco samples with fetched benign HTML)"
        samples = load_phishtank(args.phishtank) + load_openphish(args.openphish) + tranco_samples
        return samples, mode

    return build_synthetic_legacy_pool(n_each=args.synthetic_n), "synthetic (illustrative only)"


def _format_example_md(title: str, example: dict | None, score_keys: list[str]) -> str:
    if example is None:
        return f"### {title}\n\nNo matching example found in this run.\n"
    lines = [f"### {title}", "", f"- URL: `{example['url']}`"]
    for key in score_keys:
        lines.append(f"- {key}: {example[key]:.3f}" if isinstance(example[key], float) else f"- {key}: {example[key]}")
    lines.append("- Judge reasons:")
    for reason in example["reasons"]:
        lines.append(f"  - {reason}")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace, output_dir: Path) -> None:
    """Generate every Phase 7 report asset into `output_dir`. Separated
    from `main()` so tests can point it at a tmp_path instead of the
    repo's real `reports/`.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    legacy_samples, legacy_mode = _load_legacy_samples(args)
    if args.llm_generated:
        llm_samples = load_llm_generated(args.llm_generated)
        llm_mode = f"real (loaded from {args.llm_generated})"
    else:
        llm_samples = generate_llm_phishing_dataset()
        llm_mode = "mocked (generated fresh, illustrative only)"
    mode = f"legacy: {legacy_mode}; llm_generated: {llm_mode}"
    print(f"=== running with {mode} ({len(legacy_samples)} legacy + {len(llm_samples)} llm samples) ===")

    # --- dataset stats ---
    stats = dataset_stats(legacy_samples + llm_samples)
    stats.to_csv(output_dir / "phase7_dataset_stats.csv", index=False)
    print("\n=== dataset stats ===")
    print(stats.to_string(index=False))

    # --- Phase 3: legacy-only baseline vs. LLM-generated ---
    partitions = build_partitions(legacy_samples, llm_samples, test_size=args.test_size, seed=args.seed)
    baseline_model = train_classifier(build_feature_dataframe(partitions.train))
    legacy_test_df = build_feature_dataframe(partitions.legacy_test)
    llm_holdout_df = build_feature_dataframe(partitions.llm_holdout)
    phase3_comparison = compare_partitions(
        baseline_model, {"legacy_test": legacy_test_df, "llm_generated_holdout": llm_holdout_df}
    )
    phase3_comparison.to_csv(output_dir / "phase7_phase3_eval.csv", index=False)
    plot_partition_comparison(phase3_comparison, output_dir / "phase7_phase3_eval.png")
    print("\n=== Phase 3 eval (legacy-only baseline) ===")
    print(phase3_comparison.to_string(index=False))

    # --- Phase 4: mitigation + ablation ---
    result = run_mitigation_experiment(
        legacy_samples,
        llm_samples,
        fold_fraction=args.fold_fraction,
        test_size=args.test_size,
        seed=args.seed,
        alpha=args.alpha,
        judge_log_path=output_dir / "phase7_judge_log.jsonl",
    )
    result.before_after.to_csv(output_dir / "phase7_phase4_before_after.csv", index=False)
    result.ablation.to_csv(output_dir / "phase7_phase4_ablation.csv", index=False)
    plot_grouped_metric(
        result.before_after, x_col="partition", hue_col="model", metric="recall",
        out_path=output_dir / "phase7_phase4_before_after_recall.png",
        title="Recall before vs. after folding in LLM-generated samples",
    )
    plot_grouped_metric(
        result.ablation, x_col="partition", hue_col="variant", metric="recall",
        out_path=output_dir / "phase7_phase4_ablation_recall.png",
        title="Recall: classifier-only vs. classifier+judge fusion",
    )
    print("\n=== Phase 4 before/after ===")
    print(result.before_after.to_string(index=False))
    print("\n=== Phase 4 ablation ===")
    print(result.ablation.to_string(index=False))

    # --- qualitative examples ---
    legacy_catch = find_legacy_catch_example(result.before_model, result.legacy_test_df)
    llm_flip = (
        find_llm_flip_example(result.before_model, result.after_model, result.llm_holdout_df)
        if result.llm_holdout_df is not None
        else None
    )

    md = [
        "# Phase 7 qualitative examples",
        "",
        f"Run mode: **{mode}**.",
        "",
        _format_example_md(
            "Legacy phishing correctly caught (before model)",
            legacy_catch,
            ["classifier_score", "risk_score"],
        ),
        _format_example_md(
            "LLM-generated sample missed by baseline, caught after mitigation",
            llm_flip,
            ["before_score", "after_score", "risk_score"],
        ),
    ]
    (output_dir / "phase7_qualitative_examples.md").write_text("\n".join(md))
    print("\n=== qualitative examples ===")
    print("\n".join(md))

    print(f"\nwrote report assets to {output_dir}/")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phishtank", default=None)
    parser.add_argument("--openphish", default=None)
    parser.add_argument("--tranco", default=None)
    parser.add_argument("--tranco-limit", type=int, default=5000)
    parser.add_argument(
        "--tranco-html", default=None,
        help="optional JSONL of Tranco samples with fetched benign HTML (see fetch_tranco_html.py); "
        "merged into --tranco by URL, replacing the html=None versions of those domains",
    )
    parser.add_argument("--llm-generated", default=None, help="path to a saved JSONL partition; regenerates if omitted")
    parser.add_argument("--synthetic-n", type=int, default=40, help="samples per class for the synthetic legacy pool")
    parser.add_argument("--fold-fraction", type=float, default=0.5)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument(
        "--alpha", type=float, default=0.7,
        help="classifier weight in judge fusion (default 0.7 -- 0.5 collapses recall on real "
        "phishing data, see mitigation.run_mitigation_experiment's docstring)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default=str(REPORTS_DIR))
    args = parser.parse_args()

    run(args, Path(args.output_dir))


if __name__ == "__main__":
    main()
