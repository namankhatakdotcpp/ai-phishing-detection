"""Unified sample schema shared by every dataset loader and the feature pipeline.

Every loader (PhishTank, OpenPhish, Tranco, LLM-generated) must normalize its
source data into this shape before it reaches feature extraction. This keeps
the feature extractors source-agnostic and makes it possible to hold out the
LLM-generated partition using the same `source` field rather than a separate
code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Source(str, Enum):
    PHISHTANK = "phishtank"
    OPENPHISH = "openphish"
    TRANCO = "tranco"
    LLM_GENERATED = "llm_generated"


@dataclass(frozen=True)
class Sample:
    """A single labeled sample prior to feature extraction.

    `html` is optional because benign Tranco entries are URL-only until a
    snapshot is fetched; feature extraction degrades gracefully to
    URL-only features when `html` is None.
    """

    url: str
    label: int  # 1 = phishing, 0 = benign
    source: Source
    html: str | None = None
    brand_target: str | None = None  # e.g. "paypal" for LLM-generated samples

    def __post_init__(self) -> None:
        if self.label not in (0, 1):
            raise ValueError(f"label must be 0 or 1, got {self.label}")
        if not self.url:
            raise ValueError("url must be non-empty")
