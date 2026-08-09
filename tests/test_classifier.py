import numpy as np
import pandas as pd
import pytest

from phishshield.models.classifier import predict_scores, train_classifier


def _separable_df(n=60, seed=0):
    """A synthetic feature dataframe with a clearly learnable signal:
    label correlates strongly with `num_password_fields` and
    `has_external_form_action`, plus noise columns the model should mostly
    ignore. Not meant to look like real data — just fast, deterministic,
    and separable enough to sanity-check the classifier wiring.
    """
    rng = np.random.RandomState(seed)
    half = n // 2
    phishing = pd.DataFrame(
        {
            "num_password_fields": rng.poisson(1, half) + 1,
            "has_external_form_action": rng.binomial(1, 0.9, half),
            "url_length": rng.normal(60, 10, half),
            "noise": rng.normal(0, 1, half),
            "label": 1,
        }
    )
    benign = pd.DataFrame(
        {
            "num_password_fields": rng.poisson(0.1, half),
            "has_external_form_action": rng.binomial(1, 0.05, half),
            "url_length": rng.normal(20, 5, half),
            "noise": rng.normal(0, 1, half),
            "label": 0,
        }
    )
    df = pd.concat([phishing, benign], ignore_index=True)
    df["source"] = "synthetic"
    df["url"] = [f"https://sample{i}.example" for i in range(len(df))]
    return df


def test_train_classifier_rejects_single_class():
    df = _separable_df()
    df["label"] = 1
    with pytest.raises(ValueError):
        train_classifier(df)


def test_train_and_predict_round_trip():
    df = _separable_df()
    model = train_classifier(df)
    scores = predict_scores(model, df)

    assert len(scores) == len(df)
    assert scores.index.equals(df.index)
    assert scores.between(0, 1).all()


def test_classifier_learns_the_separable_signal():
    train_df = _separable_df(n=200, seed=1)
    test_df = _separable_df(n=80, seed=2)

    model = train_classifier(train_df)
    scores = predict_scores(model, test_df)
    preds = (scores >= 0.5).astype(int)

    accuracy = (preds.values == test_df["label"].values).mean()
    assert accuracy > 0.85
