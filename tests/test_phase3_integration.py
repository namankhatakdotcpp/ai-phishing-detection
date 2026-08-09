"""End-to-end Phase 3 check: real feature extraction -> partitioning ->
training -> evaluation, using the same fixtures/generator as earlier phases
(no real downloaded datasets required).
"""

from pathlib import Path

import pandas as pd

from phishshield.data.generation import generate_llm_phishing_dataset
from phishshield.data.pipeline import build_feature_dataframe
from phishshield.data.schema import Sample, Source
from phishshield.data.splits import build_partitions
from phishshield.models.classifier import train_classifier
from phishshield.models.evaluate import compare_partitions
from phishshield.models.report import plot_partition_comparison

FIXTURES = Path(__file__).parent / "fixtures"


def _legacy_pool(n_each=40):
    phishing_html = (FIXTURES / "phishing_paypal_clone.html").read_text()
    benign_html = (FIXTURES / "benign_example.html").read_text()

    phishing = [
        Sample(
            url=f"https://phish-login-{i}.verify-account.xyz/signin",
            label=1,
            source=Source.PHISHTANK,
            html=phishing_html,
        )
        for i in range(n_each)
    ]
    benign = [
        Sample(
            url=f"https://benign-site-{i}.example.com",
            label=0,
            source=Source.TRANCO,
            html=benign_html,
        )
        for i in range(n_each)
    ]
    return phishing + benign


def test_full_phase3_pipeline_runs_end_to_end(tmp_path):
    legacy = _legacy_pool()
    llm_samples = generate_llm_phishing_dataset()

    partitions = build_partitions(legacy, llm_samples, test_size=0.25, seed=42)

    train_df = build_feature_dataframe(partitions.train)
    legacy_test_df = build_feature_dataframe(partitions.legacy_test)
    llm_holdout_df = build_feature_dataframe(partitions.llm_holdout)

    model = train_classifier(train_df)

    comparison = compare_partitions(
        model, {"legacy_test": legacy_test_df, "llm_generated_holdout": llm_holdout_df}
    )

    assert list(comparison["partition"]) == ["legacy_test", "llm_generated_holdout"]
    assert (comparison["n_samples"] > 0).all()
    for col in ("precision", "recall", "f1"):
        assert comparison[col].between(0, 1).all()

    # llm_generated_holdout is phishing-only by construction (Phase 2), so
    # it has no true negatives -> FPR is structurally undefined there.
    legacy_fpr = comparison.set_index("partition").loc["legacy_test", "fpr"]
    llm_fpr = comparison.set_index("partition").loc["llm_generated_holdout", "fpr"]
    assert 0.0 <= legacy_fpr <= 1.0
    assert pd.isna(llm_fpr)

    # the legacy-shaped test fixture is exactly what the model trained on,
    # so it should be caught near-perfectly
    legacy_row = comparison.set_index("partition").loc["legacy_test"]
    assert legacy_row["recall"] > 0.9

    plot_path = tmp_path / "phase3_comparison.png"
    plot_partition_comparison(comparison, plot_path)
    assert plot_path.exists()
