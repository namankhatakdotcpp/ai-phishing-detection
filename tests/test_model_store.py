from pathlib import Path

import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from phishshield.api.model_store import DEFAULT_ARTIFACT_PATH, get_demo_model, get_model_version
from phishshield.data.schema import Sample, Source
from phishshield.features.pipeline import extract_features
from phishshield.models.classifier import predict_feature_dict

pytestmark = pytest.mark.skipif(
    not DEFAULT_ARTIFACT_PATH.exists(),
    reason=f"{DEFAULT_ARTIFACT_PATH} not committed/generated in this checkout",
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_artifact_loads_as_a_classifier():
    model = get_demo_model()
    assert isinstance(model, HistGradientBoostingClassifier)


def test_feature_ordering_matches_the_pipeline_schema():
    # The model's own recorded training columns must be a subset of what
    # the real feature pipeline produces -- if the pipeline's feature set
    # ever changes without retraining, this catches the drift instead of
    # predict_feature_dict silently zero-filling missing columns.
    model = get_demo_model()
    dummy = Sample(url="https://example.com/", label=0, source=Source.TRANCO)
    pipeline_cols = set(feature_columns_from_dict(extract_features(dummy)))
    model_cols = set(model.feature_names_in_)
    assert model_cols <= pipeline_cols


def feature_columns_from_dict(d: dict) -> list[str]:
    return list(d.keys())


def test_benign_fixture_scores_lower_than_phishing_fixture():
    # Directional check only -- NOT a hard >=0.5 phishing / <0.5 benign
    # threshold on the raw classifier score. The real, measured
    # classifier-only FPR on held-out real data is ~21.7% (see
    # PROJECT_BRIEF.md, Phase 9), so a single hand-picked benign fixture
    # landing above 0.5 on the classifier ALONE is expected, not a bug --
    # what the product actually ships is the classifier+judge fusion
    # (alpha=0.7), which is what test_api.py's end-to-end test checks.
    model = get_demo_model()
    benign_html = (FIXTURES / "benign_example.html").read_text()
    phishing_html = (FIXTURES / "phishing_paypal_clone.html").read_text()

    benign = Sample(url="https://example.com/", label=0, source=Source.TRANCO, html=benign_html)
    phishing = Sample(
        url="https://paypa1-secure.tk/login", label=1, source=Source.PHISHTANK, html=phishing_html
    )

    benign_score = predict_feature_dict(model, extract_features(benign))
    phishing_score = predict_feature_dict(model, extract_features(phishing))

    assert benign_score < phishing_score
    assert phishing_score >= 0.5


def test_scores_are_valid_probabilities():
    model = get_demo_model()
    dummy = Sample(url="https://example.com/some/page?x=1", label=0, source=Source.TRANCO)
    score = predict_feature_dict(model, extract_features(dummy))
    assert 0.0 <= score <= 1.0


def test_get_model_version_returns_a_short_stable_id():
    version = get_model_version()
    assert version is not None
    assert len(version) == 12
    assert version == get_model_version()  # stable across calls


def test_get_model_version_returns_none_for_missing_artifact():
    assert get_model_version(Path("artifacts/does-not-exist.joblib")) is None


def test_predict_feature_dict_reindexes_reordered_and_partial_features():
    # Explicit feature-ordering-mismatch check: predict_feature_dict must
    # reindex to the model's own recorded column order regardless of the
    # order/completeness of the input dict, since API callers (the
    # extension's page_extractor.js) build the dict independently and
    # dict key order is never guaranteed to match training order.
    model = get_demo_model()
    dummy = Sample(url="https://example.com/some/page?x=1", label=0, source=Source.TRANCO)
    canonical_features = extract_features(dummy)

    # Same values, keys inserted in reverse order.
    reordered = dict(reversed(list(canonical_features.items())))
    # Drop half the keys (simulates a caller sending a partial feature set).
    partial = dict(list(canonical_features.items())[: len(canonical_features) // 2])
    # Add an unexpected extra key a caller might send.
    with_extra = dict(canonical_features, unexpected_future_feature=1.0)

    canonical_score = predict_feature_dict(model, canonical_features)
    reordered_score = predict_feature_dict(model, reordered)
    extra_score = predict_feature_dict(model, with_extra)

    assert reordered_score == canonical_score
    assert extra_score == canonical_score
    partial_score = predict_feature_dict(model, partial)
    assert 0.0 <= partial_score <= 1.0  # doesn't crash; missing cols fill with 0.0
