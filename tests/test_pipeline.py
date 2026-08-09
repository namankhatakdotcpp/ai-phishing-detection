from pathlib import Path

import pytest

from phishshield.data.pipeline import build_feature_dataframe
from phishshield.data.schema import Sample, Source

FIXTURES = Path(__file__).parent / "fixtures"


def _samples():
    phishing_html = (FIXTURES / "phishing_paypal_clone.html").read_text()
    benign_html = (FIXTURES / "benign_example.html").read_text()
    return [
        Sample(
            url="https://paypal-secure-login.verify-account.xyz/login",
            label=1,
            source=Source.PHISHTANK,
            html=phishing_html,
        ),
        Sample(
            url="https://example.com/",
            label=0,
            source=Source.TRANCO,
            html=benign_html,
        ),
    ]


def test_pipeline_produces_clean_dataframe():
    df = build_feature_dataframe(_samples())
    assert len(df) == 2
    assert "label" in df.columns
    assert "source" in df.columns
    assert set(df["label"]) == {0, 1}


def test_pipeline_rejects_empty_input():
    with pytest.raises(ValueError):
        build_feature_dataframe([])


def test_no_label_leakage_into_features():
    """Feature extraction must not see or use `label` — verified by checking
    that two samples differing ONLY in label produce identical feature rows.
    """
    html = (FIXTURES / "benign_example.html").read_text()
    same_url_diff_label = [
        Sample(url="https://example.com/", label=0, source=Source.TRANCO, html=html),
        Sample(url="https://example.com/", label=1, source=Source.PHISHTANK, html=html),
    ]
    df = build_feature_dataframe(same_url_diff_label)
    feature_cols = [c for c in df.columns if c not in ("label", "source", "url")]
    row0 = df.loc[0, feature_cols]
    row1 = df.loc[1, feature_cols]
    assert row0.equals(row1)
