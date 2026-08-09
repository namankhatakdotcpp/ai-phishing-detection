from typing import Dict, List, Optional

from pydantic import BaseModel, model_validator


class AnalyzeRequest(BaseModel):
    """Exactly one of `sample_id` (score a curated demo sample) or
    `features` (score a caller-precomputed feature set) must be given.
    """

    sample_id: Optional[str] = None
    features: Optional[Dict[str, float]] = None

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


class DemoSampleMeta(BaseModel):
    id: str
    display_name: str
    label: int
