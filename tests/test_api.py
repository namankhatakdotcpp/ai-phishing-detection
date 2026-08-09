from fastapi.testclient import TestClient

from phishshield.api.app import app
from phishshield.api.demo_data import CURATED_DEMO_SAMPLES

client = TestClient(app)


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
