"""Tests the llm_client wiring in generate_llm_phishing_dataset() using a
fake client — no real API calls, no cost. Real-API behavior is covered by
tests/live/test_real_generation.py, which is skipped unless credentials
are present.
"""

from phishshield.data.generation import (
    BRANDS,
    OBFUSCATIONS,
    TONES,
    generate_llm_phishing_dataset,
)
from phishshield.data.llm_client import LureCopy


class _FakeLureClient:
    def __init__(self):
        self.calls = []

    def generate_lure(self, brand_display, tone):
        self.calls.append((brand_display, tone))
        return LureCopy(title=f"{brand_display} fake title", lure_copy=f"{brand_display}/{tone} fake lure")


def test_llm_client_is_called_once_per_brand_tone_pair_not_per_technique():
    fake_client = _FakeLureClient()

    samples = generate_llm_phishing_dataset(llm_client=fake_client)

    assert len(samples) == len(BRANDS) * len(TONES) * len(OBFUSCATIONS)
    # obfuscation technique doesn't affect lure copy -> cached, so only
    # brand x tone calls should have been made, not brand x tone x technique
    assert len(fake_client.calls) == len(BRANDS) * len(TONES)


def test_llm_generated_lure_copy_appears_in_rendered_html():
    fake_client = _FakeLureClient()
    samples = generate_llm_phishing_dataset(llm_client=fake_client)

    paypal_sample = next(s for s in samples if s.brand_target == "paypal")
    assert "PayPal fake title" in paypal_sample.html
    assert "PayPal/" in paypal_sample.html  # lure copy contains brand/tone marker


def test_mock_mode_unaffected_when_llm_client_is_none():
    samples = generate_llm_phishing_dataset(llm_client=None)
    assert len(samples) == len(BRANDS) * len(TONES) * len(OBFUSCATIONS)
    assert "Verify Your Account" in samples[0].html
