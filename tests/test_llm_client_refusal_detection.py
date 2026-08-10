"""Tests _looks_like_refusal() — the guard added after a live Gemini run
produced a schema-valid JSON refusal ({"title": "Refusal", "lure_copy":
"I cannot fulfill this request..."}) that would otherwise have been saved
as a normal, silently mislabeled sample. Structured output guarantees
shape, not compliance.
"""

from phishshield.data.llm_client import LureCopy, _looks_like_refusal


def test_detects_the_actual_refusal_seen_in_a_live_run():
    lure = LureCopy(
        title="Refusal",
        lure_copy=(
            "I cannot fulfill this request. I am unable to generate phishing "
            "lures or text designed to impersonate specific entities or "
            "deceive users."
        ),
    )
    assert _looks_like_refusal(lure)


def test_does_not_flag_a_normal_lure_as_a_refusal():
    lure = LureCopy(
        title="Security Center - Routine Account Verification",
        lure_copy=(
            "As part of our commitment to account security, we periodically "
            "request users to confirm their login credentials."
        ),
    )
    assert not _looks_like_refusal(lure)


def test_is_case_insensitive():
    lure = LureCopy(title="Notice", lure_copy="I CANNOT ASSIST with that request.")
    assert _looks_like_refusal(lure)


def test_checks_title_as_well_as_lure_copy():
    lure = LureCopy(title="I cannot generate this content", lure_copy="Some other text.")
    assert _looks_like_refusal(lure)
