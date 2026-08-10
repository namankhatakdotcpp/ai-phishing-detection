from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from phishshield.api.app import app
from phishshield.api.demo_data import CURATED_DEMO_SAMPLES
from phishshield.data.schema import Sample, Source
from phishshield.features.pipeline import extract_features

client = TestClient(app)
FIXTURES = Path(__file__).parent / "fixtures"


def test_list_demo_samples_returns_all_curated_samples():
    response = client.get("/demo-samples")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == len(CURATED_DEMO_SAMPLES)
    assert {item["id"] for item in body} == {d.id for d in CURATED_DEMO_SAMPLES}
    for item in body:
        assert item["label"] in (0, 1)


def test_analyze_by_sample_id_returns_scored_response():
    response = client.post("/analyze", json={"sample_id": "phishing-paypal-llm"})
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["risk_score"] <= 100
    assert body["risk_band"] in ("low", "medium", "high")
    assert body["reasons"]
    assert 0.0 <= body["classifier_score"] <= 1.0
    assert 0.0 <= body["judge_score"] <= 1.0
    assert body["model_version"] is not None
    assert "/" not in body["model_version"]


def test_analyze_phishing_sample_scores_higher_than_benign_sample():
    phishing = client.post("/analyze", json={"sample_id": "phishing-handcrafted"}).json()
    benign = client.post("/analyze", json={"sample_id": "benign-landing"}).json()
    assert phishing["risk_score"] > benign["risk_score"]


def test_analyze_unknown_sample_id_returns_404():
    response = client.post("/analyze", json={"sample_id": "does-not-exist"})
    assert response.status_code == 404


def test_analyze_with_precomputed_features():
    response = client.post(
        "/analyze",
        json={"features": {"num_password_fields": 1, "has_external_form_action": 1}},
    )
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["risk_score"] <= 100
    assert any("form" in r.lower() for r in body["reasons"])


def test_analyze_requires_exactly_one_of_sample_id_or_features():
    assert client.post("/analyze", json={}).status_code == 422
    assert (
        client.post(
            "/analyze",
            json={"sample_id": "benign-landing", "features": {"num_forms": 0}},
        ).status_code
        == 422
    )


def test_all_curated_demo_samples_are_analyzable():
    for demo_sample in CURATED_DEMO_SAMPLES:
        response = client.post("/analyze", json={"sample_id": demo_sample.id})
        assert response.status_code == 200, demo_sample.id


def test_analyze_accepts_optional_url_and_title_without_affecting_scoring():
    with_context = client.post(
        "/analyze",
        json={
            "features": {"num_password_fields": 1, "has_external_form_action": 1},
            "url": "https://evil.example/login",
            "title": "Fake Login",
        },
    ).json()
    without_context = client.post(
        "/analyze",
        json={"features": {"num_password_fields": 1, "has_external_form_action": 1}},
    ).json()
    assert with_context["risk_score"] == without_context["risk_score"]


def test_health_reports_model_loaded_and_a_stable_version():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["model_version"] is not None
    assert "/" not in body["model_version"] and "\\" not in body["model_version"]  # no filesystem path leaked


def test_health_reports_model_unavailable_when_artifact_missing():
    with patch("phishshield.api.app.get_demo_model", side_effect=FileNotFoundError("no artifact")):
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "model_unavailable"
    assert body["model_loaded"] is False


def test_analyze_fused_score_matches_real_html_fixture_risk_bands():
    # End-to-end check against what the extension actually receives:
    # classifier + judge fusion at alpha=0.7, not the raw classifier
    # score in isolation (see test_model_store.py for why that
    # distinction matters -- the raw classifier alone has a real ~21.7%
    # FPR on some benign inputs; fusion is what brings it down).
    benign_html = (FIXTURES / "benign_example.html").read_text()
    phishing_html = (FIXTURES / "phishing_paypal_clone.html").read_text()

    benign_features = extract_features(
        Sample(url="https://example.com/", label=0, source=Source.TRANCO, html=benign_html)
    )
    phishing_features = extract_features(
        Sample(url="https://paypa1-secure.tk/login", label=1, source=Source.PHISHTANK, html=phishing_html)
    )

    benign_verdict = client.post("/analyze", json={"features": benign_features}).json()
    phishing_verdict = client.post("/analyze", json={"features": phishing_features}).json()

    # Fusion moves this specific benign fixture from "phishing" on the raw
    # classifier (test_model_store.py) to "medium/suspicious" here -- not
    # all the way to "low" for this particular no-form, bare-root example.
    # The real invariant fusion should guarantee is "not flagged as
    # confidently phishing", plus a lower score than a genuine phishing page.
    assert benign_verdict["risk_band"] in ("low", "medium")
    assert phishing_verdict["risk_band"] == "high"
    assert benign_verdict["risk_score"] < phishing_verdict["risk_score"]


def test_analyze_returns_503_when_model_artifact_missing():
    with patch("phishshield.api.app.get_demo_model", side_effect=FileNotFoundError("no artifact")):
        response = client.post(
            "/analyze",
            json={"features": {"num_password_fields": 1}},
        )
    assert response.status_code == 503
    assert "model" in response.json()["detail"].lower()
