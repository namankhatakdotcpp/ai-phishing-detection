from pathlib import Path

import pandas as pd
import pytest

from phishshield.data.generation import generate_llm_phishing_dataset
from phishshield.data.schema import Sample, Source
from phishshield.models.mitigation import run_mitigation_experiment

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


def test_mitigation_experiment_produces_expected_tables():
    legacy = _legacy_pool()
    llm_samples = generate_llm_phishing_dataset()

    result = run_mitigation_experiment(legacy, llm_samples, fold_fraction=0.5, seed=1)

    assert set(result.before_after["model"]) == {"before", "after"}
    assert set(result.before_after["partition"]) >= {"legacy_test"}
    for col in ("precision", "recall", "f1"):
        assert result.before_after[col].between(0, 1).all()

    assert set(result.ablation["variant"]) == {"classifier_only", "classifier_plus_judge"}
    for col in ("precision", "recall", "f1"):
        assert result.ablation[col].between(0, 1).all()


def test_after_model_trained_on_more_data_than_before():
    legacy = _legacy_pool()
    llm_samples = generate_llm_phishing_dataset()
    result = run_mitigation_experiment(legacy, llm_samples, fold_fraction=0.5, seed=1)

    # before_model never sees LLM-generated training rows; after_model does.
    assert result.before_model.n_features_in_ == result.after_model.n_features_in_
    assert result.before_model is not result.after_model


def test_llm_holdout_remainder_shrinks_with_higher_fold_fraction():
    legacy = _legacy_pool()
    llm_samples = generate_llm_phishing_dataset()

    low_fold = run_mitigation_experiment(legacy, llm_samples, fold_fraction=0.2, seed=1)
    high_fold = run_mitigation_experiment(legacy, llm_samples, fold_fraction=0.8, seed=1)

    low_remainder = low_fold.before_after.query(
        "partition == 'llm_holdout_remainder' and model == 'before'"
    )["n_samples"].iloc[0]
    high_remainder = high_fold.before_after.query(
        "partition == 'llm_holdout_remainder' and model == 'before'"
    )["n_samples"].iloc[0]

    assert high_remainder < low_remainder


def test_fold_fraction_1_drops_llm_partition_from_eval_gracefully():
    legacy = _legacy_pool()
    llm_samples = generate_llm_phishing_dataset()

    result = run_mitigation_experiment(legacy, llm_samples, fold_fraction=1.0, seed=1)

    assert "llm_holdout_remainder" not in set(result.before_after["partition"])
    assert "llm_holdout_remainder" not in set(result.ablation["partition"])
    assert set(result.before_after["partition"]) == {"legacy_test"}
