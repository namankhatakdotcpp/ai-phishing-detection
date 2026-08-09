import pandas as pd
import pytest

from phishshield.models.report import plot_partition_comparison


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


def test_plot_partition_comparison_rejects_missing_columns():
    incomplete_df = pd.DataFrame([{"partition": "legacy_test", "precision": 0.9}])
    with pytest.raises(ValueError):
        plot_partition_comparison(incomplete_df, "/tmp/unused.png")
