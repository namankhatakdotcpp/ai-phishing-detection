"""Demo API: a single `/analyze` endpoint over precomputed features or a
curated demo sample, plus a listing endpoint for the extension's dropdown
and a `/health` endpoint for the extension to check backend availability.

Research-prototype demo, not a production security product: no live
WHOIS/SSL/DNS lookups, no arbitrary-page fetching. See PROJECT_BRIEF.md,
Phase 6/9.
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from phishshield.api import config
from phishshield.api.demo_data import CURATED_DEMO_SAMPLES, get_demo_sample
from phishshield.api.middleware import MaxBodySizeMiddleware, RateLimitMiddleware
from phishshield.api.model_store import get_demo_model, get_model_version
from phishshield.api.schemas import AnalyzeRequest, AnalyzeResponse, DemoSampleMeta, HealthResponse
from phishshield.features.pipeline import extract_features
from phishshield.judge.judge import judge_features, risk_band
from phishshield.models.classifier import predict_feature_dict

FUSION_ALPHA = 0.7  # classifier weight; matches mitigation.run_mitigation_experiment's
# default (see its docstring) -- 0.5 was found to collapse recall on real-world data

logger = logging.getLogger("phishshield.api")

config.assert_cors_configured_for_production(config.ENVIRONMENT, config.CORS_ORIGINS)

app = FastAPI(
    title="[PROJECT_NAME] demo API",
    description=(
        "Research-prototype demo endpoint. Scores either a precomputed "
        "feature set or one of a curated set of demo samples. Not a live "
        "crawler and makes no live WHOIS/SSL/DNS lookups."
    ),
)

# Local dev default (config.CORS_ORIGINS = ["*"]) matches the extension's
# chrome-extension:// origin (which varies per install) with zero setup.
# Production deployment must set PHISHSHIELD_CORS_ORIGINS explicitly (see
# the guard above) -- this is not a silent gap, it's an enforced one.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(MaxBodySizeMiddleware)


@app.middleware("http")
async def log_latency(request: Request, call_next):
    # Latency/status only -- never the request body, URL query params, or
    # feature payload. See PRIVACY_POLICY.md for the full logging contract.
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info("%s %s -> %d (%.1fms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        get_demo_model()
        return HealthResponse(status="ok", model_loaded=True, model_version=get_model_version())
    except FileNotFoundError:
        return HealthResponse(status="model_unavailable", model_loaded=False, model_version=None)


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

    try:
        model = get_demo_model()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"model unavailable: {exc}") from exc
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
        model_version=get_model_version(),
    )
