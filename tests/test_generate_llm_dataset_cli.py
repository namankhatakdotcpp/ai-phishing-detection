"""Tests the generate_llm_dataset CLI's dry-run and mock paths. Never
exercises --live — that requires real credentials and is covered by
tests/live/test_real_generation.py (skipped by default).
"""

import argparse
import subprocess
import sys

import pytest

from phishshield.data.generate_llm_dataset import _estimate_cost_usd, _print_dry_run


def test_estimate_cost_usd_known_model_is_positive():
    cost = _estimate_cost_usd("claude-opus-5", num_calls=12)
    assert cost is not None
    assert cost > 0


def test_estimate_cost_usd_scales_with_call_count():
    low = _estimate_cost_usd("claude-opus-5", num_calls=1)
    high = _estimate_cost_usd("claude-opus-5", num_calls=100)
    assert high > low


def test_estimate_cost_usd_unknown_model_returns_none():
    assert _estimate_cost_usd("some-unknown-model", num_calls=12) is None


def test_print_dry_run_does_not_raise(capsys):
    args = argparse.Namespace(model="claude-opus-5", effort="low", max_samples=None)
    _print_dry_run(args)
    out = capsys.readouterr().out
    assert "dry run" in out
    assert "no API calls made" in out


def test_dry_run_cli_exits_cleanly_with_no_network_and_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = subprocess.run(
        [sys.executable, "-m", "phishshield.data.generate_llm_dataset", "--dry-run", "--max-samples", "5"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "dry run" in result.stdout
    assert "unique lure-copy API calls" in result.stdout
