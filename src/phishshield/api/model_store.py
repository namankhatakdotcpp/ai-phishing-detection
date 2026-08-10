"""Loads the classifier backing the demo API.

Previously trained a small self-contained model from
`phishshield.data.synthetic`'s legacy patterns + the mocked LLM-generated
partition. That model was found (Phase 6 Sprint 1 live-page testing) to
give backwards verdicts on realistic inputs -- its tiny, template-derived
training set let it latch onto spurious numeric splits (e.g. URL path
length) instead of the intended structural signals (password field,
external form action), so it scored a textbook phishing fixture as
benign and vice versa. Replaced with the same classifier backing the
real Phase 3/4/9 results, serialized by
`phishshield.models.export_demo_model` to `artifacts/phishing_classifier.joblib`
and committed (the artifact holds only fitted split thresholds over the
feature schema, not the raw training data, so it's safe to commit even
though the datasets it was trained from are gitignored).
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Optional

import joblib
from sklearn.ensemble import HistGradientBoostingClassifier

DEFAULT_ARTIFACT_PATH = Path("artifacts/phishing_classifier.joblib")

_MISSING_ARTIFACT_HINT = (
    "Generate it with:\n"
    "  python -m phishshield.models.export_demo_model "
    "--phishtank data/raw/phishtank.csv --openphish data/raw/openphish.txt "
    "--tranco data/raw/tranco.csv --tranco-html data/generated/tranco_benign_html.jsonl "
    "--llm-generated data/generated/llm_phishing_v1.jsonl"
)


@lru_cache(maxsize=1)
def get_demo_model(artifact_path: Path = DEFAULT_ARTIFACT_PATH) -> HistGradientBoostingClassifier:
    """Load the demo classifier once per process.

    Raises `FileNotFoundError` with a clear fix rather than silently
    falling back to a lower-quality model -- an unflagged fallback is how
    the previous backwards-verdict bug went unnoticed.
    """
    if not artifact_path.exists():
        raise FileNotFoundError(f"{artifact_path} not found. {_MISSING_ARTIFACT_HINT}")
    return joblib.load(artifact_path)


def get_model_version(artifact_path: Path = DEFAULT_ARTIFACT_PATH) -> Optional[str]:
    """A short, stable identifier for the currently-loaded artifact --
    first 12 hex chars of its content hash. Not a filesystem path (never
    exposed over the API) and not a claim about training data provenance,
    just enough to tell "same build" from "different build" across
    /health calls or bug reports.
    """
    if not artifact_path.exists():
        return None
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    return digest[:12]
