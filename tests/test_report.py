import pandas as pd
import pytest

from phishshield.models.report import plot_grouped_metric, plot_partition_comparison


def test_plot_partition_comparison_writes_file(tmp_path):
    comparison_df = pd.DataFrame(
        [
            {"partition": "legacy_test", "n_samples": 40, "precision": 0.95,
             "recall": 0.92, "f1": 0.93, "fpr": 0.02},
            {"partition": "llm_holdout", "n_samples": 48, "precision": 0.61,
             "recall": 0.55, "f1": 0.58, "fpr": 0.10},
        ]
    )
    out_path = tmp_path / "comparison.png"

    plot_partition_comparison(comparison_df, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_partition_comparison_rejects_missing_columns(tmp_path):
    incomplete_df = pd.DataFrame([{"partition": "legacy_test", "precision": 0.9}])
    with pytest.raises(ValueError):
        plot_partition_comparison(incomplete_df, tmp_path / "unused.png")


def test_plot_grouped_metric_writes_file(tmp_path):
    df = pd.DataFrame(
        [
            {"model": "before", "partition": "legacy_test", "recall": 0.95},
            {"model": "after", "partition": "legacy_test", "recall": 0.96},
            {"model": "before", "partition": "llm_holdout_remainder", "recall": 0.55},
            {"model": "after", "partition": "llm_holdout_remainder", "recall": 0.88},
        ]
    )
    out_path = tmp_path / "before_after.png"

    plot_grouped_metric(df, x_col="partition", hue_col="model", metric="recall", out_path=out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_grouped_metric_rejects_missing_columns(tmp_path):
    df = pd.DataFrame([{"partition": "legacy_test", "recall": 0.9}])
    with pytest.raises(ValueError):
        plot_grouped_metric(df, x_col="partition", hue_col="model", metric="recall", out_path=tmp_path / "x.png")
