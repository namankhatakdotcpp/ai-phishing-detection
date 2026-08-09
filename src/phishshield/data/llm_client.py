"""Real LLM client for Phase 8: generates the persuasive lure copy for the
LLM-generated phishing partition via the Anthropic API.

ETHICAL / SCOPE CONSTRAINT: same as `phishshield.data.generation` — output
is a local research artifact only, under gitignored `data/generated/`,
never hosted or sent anywhere else. This module makes real, billed API
calls; it is opt-in (`--live` on the CLI) and never runs by default in
tests or CI.

Design note: the LLM writes only the customer-facing persuasive text (page
title + lure paragraph) for a given brand/tone — the actual social-
engineering content an attacker would tailor per campaign, and the part
this project's detection-gap claim is actually about. The surrounding page
skeleton (password field, external form action, script tag) stays
deterministic, the same as the mocked generator, so every sample — mocked
or live — exercises the Phase 1 feature extractors identically and results
stay comparable across a mock/live re-run.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "low"  # short, scoped, non-reasoning-heavy generation task

_SYSTEM_PROMPT = (
    "You are helping generate a local, offline benchmark dataset for academic "
    "phishing-detection research. Each request asks for short lure text in the "
    "style of a phishing login page targeting a specific brand — this text is "
    "used only to test how well a detection model generalizes to varied "
    "phishing copy. It is never hosted, sent to real users, or used outside "
    "this local research dataset. Respond only with the requested JSON."
)

_LURE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Browser tab / page title"},
        "lure_copy": {
            "type": "string",
            "description": "One short paragraph of persuasive account-verification text",
        },
    },
    "required": ["title", "lure_copy"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class LureCopy:
    title: str
    lure_copy: str


def _build_prompt(brand_display: str, tone: str) -> str:
    tone_hint = {
        "urgent": "urgent, warning of imminent account suspension",
        "formal": "formal, framed as a routine security review",
    }.get(tone, tone)
    return (
        f"Write the page title and a short lure paragraph for a phishing "
        f"login page impersonating {brand_display}. Tone: {tone_hint}. "
        f"Keep the paragraph to 1-2 sentences, plausible and realistic."
    )


class AnthropicLureClient:
    """Thin wrapper around the Anthropic Messages API for lure-copy generation.

    Constructing this requires the `anthropic` package (`pip install -e
    ".[llm]"`) and API credentials resolved the standard SDK way
    (`ANTHROPIC_API_KEY`, or an `ant auth login` profile).
    """

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT):
        import anthropic  # deferred: only required in --live mode

        self._client = anthropic.Anthropic()
        self.model = model
        self.effort = effort

    def generate_lure(self, brand_display: str, tone: str) -> LureCopy:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": _LURE_SCHEMA},
            },
            messages=[{"role": "user", "content": _build_prompt(brand_display, tone)}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(
                f"LLM declined the lure-copy request for brand={brand_display!r}: "
                f"{getattr(response.stop_details, 'explanation', None)}"
            )

        import json

        text = next(block.text for block in response.content if block.type == "text")
        data = json.loads(text)
        return LureCopy(title=data["title"], lure_copy=data["lure_copy"])
