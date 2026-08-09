"""Tests build_lure_client()'s provider dispatch/validation only — never
constructs a real client (that requires the optional anthropic/google-genai
packages and credentials). Real behavior is covered by
tests/live/test_real_generation.py.
"""

import pytest

from phishshield.data.llm_client import build_lure_client


def test_build_lure_client_rejects_unknown_provider():
    with pytest.raises(ValueError, match="unknown provider"):
        build_lure_client("openai", model="gpt-4", effort=None)
