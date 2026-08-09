import pandas as pd
import pytest

from phishshield.models.classifier import train_classifier
from phishshield.models.evaluate import compare_partitions, evaluate
from tests.test_classifier import _separable_df


def test_evaluate_rejects_empty_df():
    train_df = _separable_df()
    model = train_classifier(train_df)
    with pytest.raises(ValueError):
        evaluate(model, train_df.iloc[0:0])


def test_evaluate_on_single_class_df_reports_nan_fpr_not_an_error():
    # A phishing-only test partition (like the LLM-generated holdout) has no
    # true negatives, so FPR is structurally undefined -> NaN, not a crash.
    train_df = _separable_df()
    model = train_classifier(train_df)
    phishing_only = train_df[train_df["label"] == 1]

    metrics = evaluate(model, phishing_only)

    assert metrics["n_samples"] == len(phishing_only)
    assert pd.isna(metrics["fpr"])
    assert 0.0 <= metrics["recall"] <= 1.0


def test_evaluate_returns_expected_keys_and_ranges():
    train_df = _separable_df(seed=1)
    test_df = _separable_df(seed=2)
    model = train_classifier(train_df)

    metrics = evaluate(model, test_df)

    assert metrics["n_samples"] == len(test_df)
    for key in ("precision", "recall", "f1", "fpr"):
        assert 0.0 <= metrics[key] <= 1.0


def test_evaluate_fpr_matches_manual_confusion_matrix():
    # Hand-built case: model always predicts phishing (score >= 0 always true
    # at threshold 0.0), so every benign row is a false positive -> FPR = 1.0
    train_df = _separable_df(seed=1)
    model = train_classifier(train_df)
    test_df = _separable_df(seed=2)

    metrics = evaluate(model, test_df, threshold=0.0)
    assert metrics["fpr"] == pytest.approx(1.0)
    assert metrics["recall"] == pytest.approx(1.0)


def test_compare_partitions_preserves_order_and_columns():
    train_df = _separable_df(seed=1)
    legacy_test = _separable_df(seed=2)
    llm_holdout = _separable_df(seed=3)
    model = train_classifier(train_df)

    comparison = compare_partitions(
        model, {"legacy_test": legacy_test, "llm_holdout": llm_holdout}
    )

    assert list(comparison["partition"]) == ["legacy_test", "llm_holdout"]
    assert set(comparison.columns) == {
        "partition", "n_samples", "precision", "recall", "f1", "fpr",
    }
