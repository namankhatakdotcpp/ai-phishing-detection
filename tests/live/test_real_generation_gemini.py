"""Live smoke test: makes REAL Gemini API calls (free tier by default).

Skipped automatically unless GEMINI_API_KEY or GOOGLE_API_KEY is set, so a
normal `pytest` run (CI or local) never touches the network. Run
explicitly with:

    pip install -e ".[gemini]"
    GEMINI_API_KEY=... pytest tests/live/test_real_generation_gemini.py -v

Only makes 2 API calls (max_samples capped to trigger exactly one
brand+tone lure request, doubled to also check determinism-of-shape
across two brands) — cheap by design. See PROJECT_BRIEF.md, Phase 8.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
    reason="live LLM test requires GEMINI_API_KEY/GOOGLE_API_KEY; skipped by default",
)


def test_live_generation_matches_mock_output_shape():
    from phishshield.data.generation import OBFUSCATIONS, _TONE_COPY, generate_llm_phishing_dataset
    from phishshield.data.llm_client import GeminiLureClient
    from phishshield.data.pipeline import build_feature_dataframe
    from phishshield.data.schema import Source

    client = GeminiLureClient()

    # OBFUSCATIONS has 4 techniques per (brand, tone) pair; +1 sample spills
    # into a second brand, so this makes exactly 2 real lure-copy API calls.
    samples = generate_llm_phishing_dataset(llm_client=client, max_samples=len(OBFUSCATIONS) + 1)

    assert len(samples) == len(OBFUSCATIONS) + 1
    assert all(s.label == 1 for s in samples)
    assert all(s.source == Source.LLM_GENERATED for s in samples)
    assert all(s.html for s in samples)

    # live-generated HTML should still exercise the same feature extractors
    df = build_feature_dataframe(samples)
    assert (df["num_password_fields"] >= 1).all()
    assert (df["has_external_form_action"] == 1).all()

    # lure copy should be real generated text, not the mock's fixed strings
    assert not any(_html_contains_mock_copy(s.html, _TONE_COPY) for s in samples)


def _html_contains_mock_copy(html: str, tone_copy: dict) -> bool:
    return any(copy in html for copy in tone_copy.values())
