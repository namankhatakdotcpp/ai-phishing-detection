import numpy as np
import pandas as pd

from phishshield.models.classifier import train_classifier
from phishshield.models.qualitative import find_legacy_catch_example, find_llm_flip_example
from tests.test_classifier import _separable_df


class _FakeModel:
    """A stand-in exposing just the predict_proba() surface
    predict_scores() needs, so flip-detection logic can be tested with
    exact, hand-picked scores instead of depending on what a real
    classifier happens to learn.
    """

    def __init__(self, scores):
        self.scores = np.asarray(scores, dtype=float)

    def predict_proba(self, X):
        return np.column_stack([1 - self.scores, self.scores])


def _llm_like_df():
    return pd.DataFrame(
        {
            "num_password_fields": [1, 1, 1],
            "has_external_form_action": [1, 1, 1],
            "label": [1, 1, 1],
            "source": ["llm_generated"] * 3,
            "url": ["https://a.example", "https://b.example", "https://c.example"],
        }
    )


def test_find_legacy_catch_example_returns_a_caught_phishing_row():
    train_df = _separable_df(seed=1)
    test_df = _separable_df(seed=2)
    model = train_classifier(train_df)

    example = find_legacy_catch_example(model, test_df)

    assert example is not None
    assert example["classifier_score"] >= 0.5
    assert example["url"] in set(test_df["url"])
    assert example["reasons"]


def test_find_legacy_catch_example_returns_none_when_nothing_caught():
    train_df = _separable_df(seed=1)
    test_df = _separable_df(seed=2)
    model = train_classifier(train_df)

    example = find_legacy_catch_example(model, test_df, threshold=1.1)  # impossible threshold
    assert example is None


def test_find_llm_flip_example_finds_the_flipped_row():
    df = _llm_like_df()
    before_model = _FakeModel([0.9, 0.3, 0.2])  # row 1 missed
    after_model = _FakeModel([0.95, 0.6, 0.1])  # row 1 caught, row 2 still missed

    example = find_llm_flip_example(before_model, after_model, df)

    assert example is not None
    assert example["url"] == "https://b.example"
    assert example["before_score"] == 0.3
    assert example["after_score"] == 0.6


def test_find_llm_flip_example_returns_none_when_no_row_flips():
    df = _llm_like_df()
    before_model = _FakeModel([0.9, 0.9, 0.9])
    after_model = _FakeModel([0.95, 0.95, 0.95])

    example = find_llm_flip_example(before_model, after_model, df)
    assert example is None
