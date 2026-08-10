import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from phishshield.api.config import assert_cors_configured_for_production
from phishshield.api.middleware import MaxBodySizeMiddleware, RateLimitMiddleware


def _tiny_app():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/echo")
    def echo():
        return {"ok": True}

    return app


def test_rate_limit_blocks_after_threshold():
    app = _tiny_app()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=3)
    client = TestClient(app)

    for _ in range(3):
        assert client.post("/echo").status_code == 200
    blocked = client.post("/echo")
    assert blocked.status_code == 429


def test_rate_limit_exempts_health():
    app = _tiny_app()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=1)
    client = TestClient(app)

    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_max_body_size_rejects_oversized_request():
    app = _tiny_app()
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=10)
    client = TestClient(app)

    response = client.post("/echo", content=b"x" * 100)
    assert response.status_code == 413


def test_max_body_size_allows_small_request():
    app = _tiny_app()
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=1000)
    client = TestClient(app)

    response = client.post("/echo", content=b"x" * 10)
    assert response.status_code == 200


def test_config_env_helpers_use_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("PHISHSHIELD_RATE_LIMIT_PER_MINUTE", raising=False)
    monkeypatch.delenv("PHISHSHIELD_CORS_ORIGINS", raising=False)
    from phishshield.api import config

    importlib.reload(config)
    assert config.RATE_LIMIT_PER_MINUTE == 60
    assert config.CORS_ORIGINS == ["*"]
    importlib.reload(config)  # restore for other tests


def test_production_refuses_wildcard_cors():
    with pytest.raises(RuntimeError, match="wildcard CORS"):
        assert_cors_configured_for_production("production", ["*"])


def test_production_allows_explicit_cors():
    assert_cors_configured_for_production("production", ["https://real-domain.example"]) is None


def test_development_allows_wildcard_cors():
    assert_cors_configured_for_production("development", ["*"]) is None


def test_config_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("PHISHSHIELD_RATE_LIMIT_PER_MINUTE", "5")
    monkeypatch.setenv("PHISHSHIELD_CORS_ORIGINS", "https://a.example,https://b.example")
    from phishshield.api import config

    importlib.reload(config)
    try:
        assert config.RATE_LIMIT_PER_MINUTE == 5
        assert config.CORS_ORIGINS == ["https://a.example", "https://b.example"]
    finally:
        monkeypatch.delenv("PHISHSHIELD_RATE_LIMIT_PER_MINUTE", raising=False)
        monkeypatch.delenv("PHISHSHIELD_CORS_ORIGINS", raising=False)
        importlib.reload(config)
