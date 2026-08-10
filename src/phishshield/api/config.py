"""Environment-based configuration for the demo API.

Every setting has a safe local-development default so `uvicorn
phishshield.api.app:app` keeps working with zero setup, per this
project's existing "no config needed for local use" norm. Production
deployment (Sprint 2) overrides these via real environment variables --
see `.env.example` and `LOCAL_SETUP.md`.
"""

from __future__ import annotations

import os


def _env_list(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


ENVIRONMENT = os.environ.get("PHISHSHIELD_ENV", "development")

# Local dev default stays wide open (matches the extension's
# chrome-extension:// origin, which varies per install ID). Production
# deployment MUST set PHISHSHIELD_CORS_ORIGINS explicitly -- app.py
# refuses to start with the wildcard default when PHISHSHIELD_ENV=production.
CORS_ORIGINS = _env_list("PHISHSHIELD_CORS_ORIGINS", "*")

RATE_LIMIT_PER_MINUTE = _env_int("PHISHSHIELD_RATE_LIMIT_PER_MINUTE", 60)
MAX_REQUEST_BYTES = _env_int("PHISHSHIELD_MAX_REQUEST_BYTES", 64 * 1024)  # 64 KiB


def assert_cors_configured_for_production(environment: str, cors_origins: list[str]) -> None:
    """Refuse to start with wildcard CORS when explicitly running in
    production -- a pure function so it's unit-testable without having to
    reimport the whole `app` module (which has import-time side effects).
    """
    if environment == "production" and cors_origins == ["*"]:
        raise RuntimeError(
            "PHISHSHIELD_ENV=production requires PHISHSHIELD_CORS_ORIGINS to be set "
            "explicitly (comma-separated) -- refusing to start with wildcard CORS in production."
        )
