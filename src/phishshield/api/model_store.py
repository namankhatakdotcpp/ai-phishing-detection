"""Trains the classifier backing the demo API.

This is NOT the Phase 3/4 experiment's classifier — that requires
downloaded PhishTank/OpenPhish/Tranco snapshots the demo doesn't ship
with. This is a small, self-contained model trained entirely from
`phishshield.data.synthetic`'s legacy patterns plus the mocked
LLM-generated partition (`phishshield.data.generation`), good enough to
back a live demo but not a scientific result — the report's numbers come
from `train_baseline`/`run_mitigation` against real data, not from this
module.
"""

from __future__ import annotations

from functools import lru_cache

from sklearn.ensemble import HistGradientBoostingClassifier

from phishshield.data.generation import generate_llm_phishing_dataset
from phishshield.data.pipeline import build_feature_dataframe
from phishshield.data.synthetic import build_synthetic_legacy_pool
from phishshield.models.classifier import train_classifier


@lru_cache(maxsize=1)
def get_demo_model() -> HistGradientBoostingClassifier:
    """Return the demo classifier, training it once per process."""
    train_samples = build_synthetic_legacy_pool() + generate_llm_phishing_dataset()
    train_df = build_feature_dataframe(train_samples)
    return train_classifier(train_df)
