"""Real LLM clients for Phase 8: generate the persuasive lure copy for the
LLM-generated phishing partition via a real API — Anthropic or Gemini.

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
or live, whichever provider — exercises the Phase 1 feature extractors
identically and results stay comparable across a re-run.

Only offline dataset generation calls a real LLM. The live `/analyze` path
(`phishshield.judge.judge`) stays the deterministic rule engine — see
PROJECT_BRIEF.md's Phase 8+ decisions.

CREDENTIAL HANDLING: API keys are read from the environment (optionally via
a local, gitignored `.env` file loaded below) — never pass a key as a CLI
argument or type it into a chat/agent session, both of which land the raw
secret in a transcript, shell history, or `ps aux`. Use `describe_env_key()`
to check presence/format without ever printing the full value.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv  # optional: pip install -e ".[llm]" or ".[gemini]"

    load_dotenv()  # reads a local .env into os.environ if present; no-op otherwise
except ImportError:
    pass

ANTHROPIC_DEFAULT_MODEL = "claude-opus-5"
ANTHROPIC_DEFAULT_EFFORT = "low"  # short, scoped, non-reasoning-heavy generation task

GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"  # free-tier eligible at time of writing; pass --model to override

_ENV_KEYS_BY_PROVIDER = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
}


def describe_env_key(provider: str) -> str:
    """Report whether credentials for `provider` are present, masked — for
    confirming setup in logs/CLI output without ever revealing the secret.
    """
    for env_var in _ENV_KEYS_BY_PROVIDER.get(provider, ()):
        value = os.environ.get(env_var)
        if value:
            masked = f"{value[:6]}...{value[-4:]}" if len(value) > 12 else "<set>"
            return f"{env_var} is set ({masked})"
    checked = " / ".join(_ENV_KEYS_BY_PROVIDER.get(provider, ()))
    return f"no credentials found for {provider!r} (checked {checked})"

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

    def __init__(self, model: str = ANTHROPIC_DEFAULT_MODEL, effort: str = ANTHROPIC_DEFAULT_EFFORT):
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

        text = next(block.text for block in response.content if block.type == "text")
        data = json.loads(text)
        return LureCopy(title=data["title"], lure_copy=data["lure_copy"])


class GeminiLureClient:
    """Thin wrapper around the Gemini API (`google-genai`) for lure-copy
    generation.

    Constructing this requires the `google-genai` package (`pip install -e
    ".[gemini]"`) and an API key resolved by the SDK's default client
    (`GEMINI_API_KEY` or `GOOGLE_API_KEY` env var — get a free-tier key at
    https://aistudio.google.com/apikey).
    """

    def __init__(self, model: str = GEMINI_DEFAULT_MODEL, effort: str | None = None):
        from google import genai  # deferred: only required in --live mode

        self._genai = genai
        self._client = genai.Client()
        self.model = model
        self.effort = effort  # accepted for CLI symmetry with Anthropic; unused by Gemini

    def generate_lure(self, brand_display: str, tone: str) -> LureCopy:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=_build_prompt(brand_display, tone),
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=_LURE_SCHEMA,
            ),
        )
        if not response.text:
            raise RuntimeError(
                f"Gemini returned no content for brand={brand_display!r} "
                f"(possibly blocked — check response.prompt_feedback)"
            )

        data = json.loads(response.text)
        return LureCopy(title=data["title"], lure_copy=data["lure_copy"])


def build_lure_client(provider: str, model: str, effort: str):
    """Construct the lure client for `provider` ("anthropic" | "gemini")."""
    if provider == "anthropic":
        return AnthropicLureClient(model=model, effort=effort)
    if provider == "gemini":
        return GeminiLureClient(model=model, effort=effort)
    raise ValueError(f"unknown provider: {provider!r} (expected 'anthropic' or 'gemini')")
