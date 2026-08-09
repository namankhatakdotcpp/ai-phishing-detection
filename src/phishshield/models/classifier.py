"""Baseline phishing classifier trained on legacy data only.

This is the control model for the Phase 3 headline result: it never sees
LLM-generated samples during training (that only happens in Phase 4's
mitigation experiment via `phishshield.data.splits.fold_in_llm_samples`).

Uses scikit-learn's HistGradientBoostingClassifier rather than XGBoost: it's
still a gradient-boosted tree model (matching the project brief's intent),
but has no native-library runtime dependency — XGBoost's macOS wheels
require `libomp` via Homebrew, which isn't available in every dev/CI
environment this needs to run in.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from phishshield.data.pipeline import feature_columns

DEFAULT_PARAMS = {
    "max_iter": 200,
    "max_depth": 4,
    "learning_rate": 0.1,
    "random_state": 42,
}


def train_classifier(train_df: pd.DataFrame, **params) -> HistGradientBoostingClassifier:
    """Fit a gradient-boosted tree classifier on a feature dataframe's
    model-input columns.

    Raises ValueError if `train_df` contains only one class — a classifier
    trained on a single class is meaningless and silently "succeeding" on
    it would hide a broken data split.
    """
    if train_df["label"].nunique() < 2:
        raise ValueError("train_df must contain both classes (label 0 and 1)")

    cols = feature_columns(train_df)
    model = HistGradientBoostingClassifier(**{**DEFAULT_PARAMS, **params})
    model.fit(train_df[cols], train_df["label"])
    return model


def predict_scores(model: HistGradientBoostingClassifier, df: pd.DataFrame) -> pd.Series:
    """Return phishing-class probability for each row, indexed like `df`."""
    cols = feature_columns(df)
    proba = model.predict_proba(df[cols])[:, 1]
    return pd.Series(proba, index=df.index, name="phishing_score")


def predict_feature_dict(model: HistGradientBoostingClassifier, features: dict) -> float:
    """Score a single precomputed feature dict.

    Reindexed to the columns `model` was trained on (`feature_names_in_`,
    set automatically by sklearn when `fit` sees a DataFrame): missing
    keys default to 0, extra keys are dropped. This lets API callers pass
    a partial/precomputed feature set without needing to match the
    training schema exactly, rather than failing on any column mismatch.
    """
    expected_cols = list(model.feature_names_in_)
    row = pd.DataFrame([features]).reindex(columns=expected_cols, fill_value=0.0)
    return float(model.predict_proba(row)[0, 1])
