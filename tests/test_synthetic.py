from phishshield.data.pipeline import build_feature_dataframe
from phishshield.data.schema import Source
from phishshield.data.synthetic import build_synthetic_legacy_pool


def test_build_synthetic_legacy_pool_balanced_by_label():
    pool = build_synthetic_legacy_pool(n_each=10)
    assert len(pool) == 20
    assert sum(s.label == 1 for s in pool) == 10
    assert sum(s.label == 0 for s in pool) == 10
    assert all(s.source == Source.PHISHTANK for s in pool if s.label == 1)
    assert all(s.source == Source.TRANCO for s in pool if s.label == 0)


def test_synthetic_pool_flows_through_feature_pipeline():
    pool = build_synthetic_legacy_pool(n_each=5)
    df = build_feature_dataframe(pool)
    assert len(df) == 10
    phishing_rows = df[df["label"] == 1]
    assert (phishing_rows["num_password_fields"] >= 1).all()
    assert (phishing_rows["has_external_form_action"] == 1).all()
