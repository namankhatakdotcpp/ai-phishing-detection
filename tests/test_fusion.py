import pandas as pd
import pytest

from phishshield.models.fusion import fuse_scores


def test_fuse_scores_weighted_average():
    classifier_scores = pd.Series([0.8, 0.2], index=[0, 1])
    judge_scores = pd.Series([0.4, 0.6], index=[0, 1])

    fused = fuse_scores(classifier_scores, judge_scores, alpha=0.75)

    assert fused.name == "fused_score"
    assert fused.iloc[0] == pytest.approx(0.75 * 0.8 + 0.25 * 0.4)
    assert fused.iloc[1] == pytest.approx(0.75 * 0.2 + 0.25 * 0.6)


def test_fuse_scores_alpha_1_is_classifier_only():
    classifier_scores = pd.Series([0.8, 0.2], index=[0, 1])
    judge_scores = pd.Series([0.1, 0.9], index=[0, 1])
    fused = fuse_scores(classifier_scores, judge_scores, alpha=1.0)
    assert list(fused) == list(classifier_scores)


def test_fuse_scores_rejects_out_of_range_alpha():
    s = pd.Series([0.5], index=[0])
    with pytest.raises(ValueError):
        fuse_scores(s, s, alpha=1.5)


def test_fuse_scores_rejects_misaligned_index():
    a = pd.Series([0.5, 0.6], index=[0, 1])
    b = pd.Series([0.5, 0.6], index=[1, 2])
    with pytest.raises(ValueError):
        fuse_scores(a, b)
