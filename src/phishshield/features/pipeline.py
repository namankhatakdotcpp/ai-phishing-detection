"""Combines URL and HTML feature extractors into one feature row per sample."""

from __future__ import annotations

from phishshield.data.schema import Sample
from phishshield.features.html_features import extract_html_features
from phishshield.features.url_features import extract_url_features


def extract_features(sample: Sample) -> dict:
    """Extract the full feature vector for one sample.

    Returns only feature columns — the caller is responsible for attaching
    `label`/`source` afterward, keeping label leakage impossible by
    construction (this function never sees or touches `sample.label`).
    """
    row = {}
    row.update(extract_url_features(sample.url))
    row.update(extract_html_features(sample.html, sample.url))
    return row
