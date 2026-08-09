"""Turns a list of `Sample` objects into a feature dataframe.

Feature extraction (`extract_features`) never receives `label`, so leakage
is prevented by construction rather than by convention — `label`/`source`
are attached only after the feature dict is built.
"""

from __future__ import annotations

import pandas as pd

from phishshield.data.schema import Sample
from phishshield.features.pipeline import extract_features

# Columns build_feature_dataframe appends that are not model inputs.
NON_FEATURE_COLUMNS = {"label", "source", "url"}


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the model-input columns of a feature dataframe, in order.

    Derived from the dataframe rather than hardcoded so it stays in sync
    automatically as feature extractors gain/lose columns.
    """
    return [c for c in df.columns if c not in NON_FEATURE_COLUMNS]


def build_feature_dataframe(samples: list[Sample]) -> pd.DataFrame:
    """Build a feature dataframe from samples.

    Columns: all feature columns, plus `label` and `source` appended last.
    Raises ValueError on an empty sample list rather than returning an
    ambiguous empty dataframe with no columns.
    """
    if not samples:
        raise ValueError("samples must be non-empty")

    rows = []
    for sample in samples:
        row = extract_features(sample)
        row["label"] = sample.label
        row["source"] = sample.source.value
        row["url"] = sample.url
        rows.append(row)

    return pd.DataFrame(rows)
