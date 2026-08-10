"""Tests the retry/backoff and manifest-logging helpers merged into
llm_client.py from the incoming patch — using fakes only, no real API
calls. time.sleep is monkeypatched so retry tests don't actually wait.
"""

import json

import pytest

from phishshield.data.llm_client import (
    LureGenerationError,
    _append_manifest,
    _with_retries,
)


def test_with_retries_succeeds_on_first_try():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    result, attempt = _with_retries(fn, "test call", max_retries=3)
    assert result == "ok"
    assert attempt == 1
    assert len(calls) == 1


def test_with_retries_succeeds_after_transient_failures(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    result, attempt = _with_retries(fn, "test call", max_retries=3)
    assert result == "ok"
    assert attempt == 3
    assert calls["n"] == 3


def test_with_retries_raises_lure_generation_error_after_exhausting_attempts(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    def fn():
        raise RuntimeError("permanent failure")

    with pytest.raises(LureGenerationError, match="failed after 3 attempts"):
        _with_retries(fn, "test call", max_retries=3)


def test_append_manifest_writes_one_json_record_per_call(tmp_path):
    manifest_path = tmp_path / "manifest.jsonl"

    _append_manifest(
        manifest_path, "gemini", "gemini-2.5-flash", "PayPal", "urgent",
        "prompt text", "raw response text", attempt=1,
    )
    _append_manifest(
        manifest_path, "anthropic", "claude-opus-5", "Chase Bank", "formal",
        "prompt text 2", "raw response text 2", attempt=2,
    )

    lines = manifest_path.read_text().strip().splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["provider"] == "gemini"
    assert first["brand"] == "PayPal"
    assert first["tone"] == "urgent"
    assert first["attempt"] == 1
    assert first["prompt"] == "prompt text"
    assert first["raw_response"] == "raw response text"
    assert "timestamp" in first

    second = json.loads(lines[1])
    assert second["provider"] == "anthropic"
    assert second["attempt"] == 2


def test_append_manifest_creates_parent_directory(tmp_path):
    manifest_path = tmp_path / "nested" / "dir" / "manifest.jsonl"
    _append_manifest(manifest_path, "gemini", "m", "Brand", "urgent", "p", "r", 1)
    assert manifest_path.exists()
