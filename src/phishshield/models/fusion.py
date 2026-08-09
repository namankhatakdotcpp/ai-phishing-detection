"""Combines classifier and judge scores into a single fused risk score."""

from __future__ import annotations

import pandas as pd


def fuse_scores(classifier_scores: pd.Series, judge_scores: pd.Series, alpha: float = 0.5) -> pd.Series:
    """Weighted average of classifier probability and judge risk score
    (both expected on a 0-1 scale, same index).

    `alpha` is the classifier's weight; `1 - alpha` goes to the judge.
    Raises ValueError if `alpha` is out of [0, 1] or the two Series aren't
    aligned on the same index — fusing misaligned scores would silently
    produce a meaningless number rather than an error.
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be between 0 and 1")
    if not classifier_scores.index.equals(judge_scores.index):
        raise ValueError("classifier_scores and judge_scores must share the same index")

    fused = alpha * classifier_scores + (1 - alpha) * judge_scores
    fused.name = "fused_score"
    return fused
