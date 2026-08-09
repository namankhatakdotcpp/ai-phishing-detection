"""Finds the qualitative examples the Phase 7 report writeup wants: one
legacy phishing sample correctly caught, and one LLM-generated sample that
fools the baseline ("before") model but is caught by the mitigated
("after") model.

Both finders return `None` rather than fabricating an example when no
matching row exists — per the project brief, honest negative results
belong in the report too, especially since (as documented in
PROJECT_BRIEF.md / README) the toy synthetic setup doesn't reliably
reproduce a legacy->LLM detection gap the way real downloaded data would.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from phishshield.data.pipeline import feature_columns
from phishshield.judge.judge import judge_features
from phishshield.models.classifier import predict_scores


def find_legacy_catch_example(
    model: HistGradientBoostingClassifier, legacy_test_df: pd.DataFrame, threshold: float = 0.5
) -> Optional[dict]:
    """First phishing row in `legacy_test_df` that `model` scores >= threshold."""
    scores = predict_scores(model, legacy_test_df)
    cols = feature_columns(legacy_test_df)

    phishing_rows = legacy_test_df[legacy_test_df["label"] == 1]
    for idx in phishing_rows.index:
        if scores.loc[idx] >= threshold:
            verdict = judge_features(legacy_test_df.loc[idx, cols].to_dict())
            return {
                "url": legacy_test_df.loc[idx, "url"],
                "classifier_score": float(scores.loc[idx]),
                "risk_score": verdict.risk_score,
                "reasons": verdict.reasons,
            }
    return None


def find_llm_flip_example(
    before_model: HistGradientBoostingClassifier,
    after_model: HistGradientBoostingClassifier,
    llm_df: pd.DataFrame,
    threshold: float = 0.5,
) -> Optional[dict]:
    """First row `before_model` misses (score < threshold) that `after_model`
    catches (score >= threshold) — i.e. the LLM-generated mitigation working.
    """
    before_scores = predict_scores(before_model, llm_df)
    after_scores = predict_scores(after_model, llm_df)
    cols = feature_columns(llm_df)

    for idx in llm_df.index:
        if before_scores.loc[idx] < threshold <= after_scores.loc[idx]:
            verdict = judge_features(llm_df.loc[idx, cols].to_dict())
            return {
                "url": llm_df.loc[idx, "url"],
                "before_score": float(before_scores.loc[idx]),
                "after_score": float(after_scores.loc[idx]),
                "risk_score": verdict.risk_score,
                "reasons": verdict.reasons,
            }
    return None
