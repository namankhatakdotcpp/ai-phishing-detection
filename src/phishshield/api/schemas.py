from typing import Dict, List, Optional

from pydantic import BaseModel, model_validator


class AnalyzeRequest(BaseModel):
    """Exactly one of `sample_id` (score a curated demo sample) or
    `features` (score a caller-precomputed feature set) must be given.

    `url`/`title` are optional, display-only context from the caller (e.g.
    the extension's current tab) -- never used as model input and never
    logged; the feature schema is entirely numeric (see
    `phishshield.features.pipeline.extract_features`). They exist so a
    caller can round-trip page identity through the request without the
    backend needing to infer it from `features`.
    """

    sample_id: Optional[str] = None
    features: Optional[Dict[str, float]] = None
    url: Optional[str] = None
    title: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one_input(self) -> "AnalyzeRequest":
        if (self.sample_id is None) == (self.features is None):
            raise ValueError("exactly one of sample_id or features must be provided")
        return self


class AnalyzeResponse(BaseModel):
    risk_score: int
    risk_band: str
    reasons: List[str]
    classifier_score: float
    judge_score: float
    model_version: Optional[str] = None


class DemoSampleMeta(BaseModel):
    id: str
    display_name: str
    label: int


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: Optional[str] = None
