"""Renders the headline legacy-vs-LLM-generated performance-drop plot."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — this runs in scripts/CI, never a GUI session
import matplotlib.pyplot as plt
import pandas as pd

METRICS_TO_PLOT = ("precision", "recall", "f1", "fpr")


def plot_partition_comparison(comparison_df: pd.DataFrame, out_path: str | Path) -> None:
    """Save a grouped bar chart of `comparison_df` (as built by
    `phishshield.models.evaluate.compare_partitions`) to `out_path`.

    Raises ValueError if `comparison_df` is missing the columns this plot
    depends on, so a malformed upstream table fails loudly instead of
    producing a blank or misleading chart.
    """
    required = {"partition", *METRICS_TO_PLOT}
    missing = required - set(comparison_df.columns)
    if missing:
        raise ValueError(f"comparison_df missing required columns: {sorted(missing)}")

    plot_df = comparison_df.set_index("partition")[list(METRICS_TO_PLOT)]

    ax = plot_df.plot(kind="bar", figsize=(8, 5), ylim=(0, 1))
    ax.set_ylabel("score")
    ax.set_title("Baseline classifier: legacy vs. LLM-generated phishing")
    ax.legend(title="metric", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    plt.close(ax.get_figure())
