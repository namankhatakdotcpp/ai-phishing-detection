"""Demo API: a single `/analyze` endpoint over precomputed features or a
curated demo sample, plus a listing endpoint for the extension's dropdown.

Research-prototype demo, not a production security product: no live
WHOIS/SSL/DNS lookups, no arbitrary-page fetching. See PROJECT_BRIEF.md,
Phase 6.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from phishshield.api.demo_data import CURATED_DEMO_SAMPLES, get_demo_sample
from phishshield.api.model_store import get_demo_model
from phishshield.api.schemas import AnalyzeRequest, AnalyzeResponse, DemoSampleMeta
from phishshield.features.pipeline import extract_features
from phishshield.judge.judge import judge_features, risk_band
from phishshield.models.classifier import predict_feature_dict

FUSION_ALPHA = 0.5  # classifier weight; matches the Phase 4 ablation default

app = FastAPI(
    title="PhishShield AI demo API",
    description=(
        "Research-prototype demo endpoint. Scores either a precomputed "
        "feature set or one of a curated set of demo samples. Not a live "
        "crawler and makes no live WHOIS/SSL/DNS lookups."
    ),
)

# The demo extension's popup runs from a chrome-extension:// origin and
# calls this localhost-only API. Wide open CORS is fine here: this is a
# local research demo, not a deployed service with anything to protect.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/demo-samples", response_model=list[DemoSampleMeta])
def list_demo_samples() -> list[DemoSampleMeta]:
    return [
        DemoSampleMeta(id=d.id, display_name=d.display_name, label=d.sample.label)
        for d in CURATED_DEMO_SAMPLES
    ]


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    if request.sample_id is not None:
        try:
            demo_sample = get_demo_sample(request.sample_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown sample_id: {request.sample_id!r}")
        features = extract_features(demo_sample.sample)
    else:
        features = request.features

    model = get_demo_model()
    classifier_score = predict_feature_dict(model, features)

    verdict = judge_features(features)
    judge_score = verdict.risk_score / 100

    fused_score = FUSION_ALPHA * classifier_score + (1 - FUSION_ALPHA) * judge_score
    risk_score = round(fused_score * 100)

    return AnalyzeResponse(
        risk_score=risk_score,
        risk_band=risk_band(risk_score),
        reasons=verdict.reasons,
        classifier_score=classifier_score,
        judge_score=judge_score,
    )
