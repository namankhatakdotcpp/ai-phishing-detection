"""Real LLM clients for Phase 8: generate the persuasive lure copy for the
LLM-generated phishing partition via a real API — Anthropic or Gemini.

ETHICAL / SCOPE CONSTRAINT: same as `phishshield.data.generation` — output
is a local research artifact only, under gitignored `data/generated/`,
never hosted or sent anywhere else. This module makes real, billed API
calls; it is opt-in (`--live` on the CLI) and never runs by default in
tests or CI. Every call and its raw response is appended to a local
manifest (`data/generated/generation_manifest.jsonl` by default, itself
gitignored) for methodology reproducibility — enough to answer "did
accuracy drop specifically on the `reward` tone?" during error analysis.

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
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv  # optional: pip install -e ".[llm]" or ".[gemini]"

    load_dotenv()  # reads a local .env into os.environ if present; no-op otherwise
except ImportError:
    pass

logger = logging.getLogger(__name__)

ANTHROPIC_DEFAULT_MODEL = "claude-opus-5"
ANTHROPIC_DEFAULT_EFFORT = "low"  # short, scoped, non-reasoning-heavy generation task

GEMINI_DEFAULT_MODEL = "gemini-flash-latest"  # alias tracking Google's current flash model;
# confirmed live 2026-08-10 — gemini-2.5-flash 404s for new-user keys ("no longer
# available to new users"), so pin to the alias rather than a specific dated model.

DEFAULT_MANIFEST_PATH = Path("data/generated/generation_manifest.jsonl")
DEFAULT_MAX_RETRIES = 3  # exponential backoff: 2s, 4s, 8s between attempts

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

# Gemini's response_schema uses a restricted OpenAPI subset that rejects
# additionalProperties outright (400 INVALID_ARGUMENT) — same shape as
# _LURE_SCHEMA minus that one field, kept as a separate constant rather
# than stripped ad hoc so both schemas stay easy to diff against each
# other when the shared fields change.
_GEMINI_LURE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Browser tab / page title"},
        "lure_copy": {
            "type": "string",
            "description": "One short paragraph of persuasive account-verification text",
        },
    },
    "required": ["title", "lure_copy"],
}

# One entry per tone key used in generation.py's TONES tuple. Keep this in
# sync with generation.py's _TONE_COPY/_TONE_PATH dicts — every tone in
# TONES needs a matching entry here (live) and there (mock fallback).
_TONE_INSTRUCTIONS = {
    "urgent": (
        "urgent — implies an imminent negative consequence (account "
        "suspension, lockout) unless the user acts within a short deadline"
    ),
    "formal": "formal — a routine, low-pressure security-review notice",
    "reward": (
        "reward — implies the user has a prize, refund, or benefit "
        "waiting, contingent on 'confirming' their account"
    ),
    "security_alert": (
        "security alert — claims suspicious sign-in activity was "
        "detected and asks the user to verify it was them"
    ),
    "invoice": (
        "invoice — references a pending or overdue payment/invoice "
        "that requires the user to log in to review"
    ),
    "delivery": (
        "delivery — claims a package delivery failed or requires an "
        "address/payment confirmation"
    ),
}


@dataclass(frozen=True)
class LureCopy:
    title: str
    lure_copy: str


class LureGenerationError(RuntimeError):
    """Raised when an API call or response parsing fails after retries."""


# Phrases indicating the model refused the request inside otherwise
# schema-valid JSON — structured output guarantees *shape*, not that the
# model actually complied. A refusal wrapped in {"title": "...", ...} would
# otherwise parse cleanly and get saved into the dataset as a normal,
# silently mislabeled sample. Checked case-insensitively, matched as a
# substring since refusal phrasing varies by provider/model.
_REFUSAL_MARKERS = (
    "cannot fulfill this request",
    "can't fulfill this request",
    "cannot generate",
    "can't generate",
    "unable to generate",
    "i cannot assist",
    "i can't assist",
    "i'm unable to",
    "i am unable to",
    "cannot help with that",
    "can't help with that",
    "against my guidelines",
    "i won't create",
    "i will not create",
)


def _looks_like_refusal(lure: LureCopy) -> bool:
    text = f"{lure.title} {lure.lure_copy}".lower()
    return any(marker in text for marker in _REFUSAL_MARKERS)


def _build_prompt(brand_display: str, tone: str) -> str:
    tone_hint = _TONE_INSTRUCTIONS.get(tone, tone)
    return (
        f"Write the page title and a short lure paragraph for a phishing "
        f"login page impersonating {brand_display}. Tone: {tone_hint}. "
        f"Keep the paragraph to 1-2 sentences, plausible and realistic."
    )


def _append_manifest(
    manifest_path: Path, provider: str, model: str, brand_display: str, tone: str,
    prompt: str, raw_response: str, attempt: int,
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": time.time(),
        "provider": provider,
        "model": model,
        "brand": brand_display,
        "tone": tone,
        "attempt": attempt,
        "prompt": prompt,
        "raw_response": raw_response,
    }
    with manifest_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


_RETRY_DELAY_PATTERN = re.compile(r"['\"]?retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s['\"]")


def _suggested_retry_delay(exc: BaseException) -> Optional[float]:
    """Extract the API's own suggested wait time from a 429 error, if
    present (both Anthropic's and Gemini's SDKs surface this in the
    exception's string form as a `retryDelay`-style field). Rate-limit
    windows are seconds-scale and our fixed exponential backoff (2/4/8s)
    is often shorter than what the API actually needs to clear.
    """
    match = _RETRY_DELAY_PATTERN.search(str(exc))
    return float(match.group(1)) if match else None


def _with_retries(fn, description: str, max_retries: int):
    """Call `fn()`, retrying on any exception up to `max_retries` attempts.
    Waits the API's own suggested `retryDelay` when a 429 response
    provides one (common on a per-minute rate limit, where our default
    2/4/8s backoff is too short to clear the window); otherwise falls
    back to exponential backoff (2s, 4s, 8s, ...). Returns (result,
    attempt_number) so callers can log which attempt succeeded.

    Deliberately re-raises as `LureGenerationError` rather than degrading
    silently — a pair that fails after retries should abort the run, not
    produce a sample mislabeled as live-generated when it's actually a
    parsing failure or a persistent API error.
    """
    last_error: Optional[BaseException] = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn(), attempt
        except Exception as exc:  # noqa: BLE001 - intentionally broad, see docstring
            last_error = exc
            logger.warning("%s attempt %d/%d failed: %s", description, attempt, max_retries, exc)
            if attempt < max_retries:
                delay = _suggested_retry_delay(exc)
                if delay is None:
                    delay = 2**attempt
                time.sleep(delay + 1)  # +1s safety margin past the API's own estimate
    raise LureGenerationError(f"{description} failed after {max_retries} attempts") from last_error


class AnthropicLureClient:
    """Thin wrapper around the Anthropic Messages API for lure-copy generation.

    Constructing this requires the `anthropic` package (`pip install -e
    ".[llm]"`) and API credentials resolved the standard SDK way
    (`ANTHROPIC_API_KEY`, or an `ant auth login` profile).
    """

    def __init__(
        self,
        model: str = ANTHROPIC_DEFAULT_MODEL,
        effort: str = ANTHROPIC_DEFAULT_EFFORT,
        manifest_path: Path = DEFAULT_MANIFEST_PATH,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        import anthropic  # deferred: only required in --live mode

        self._client = anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self._manifest_path = Path(manifest_path)
        self._max_retries = max_retries

    def generate_lure(self, brand_display: str, tone: str) -> LureCopy:
        prompt = _build_prompt(brand_display, tone)

        def _call():
            response = self._client.messages.create(
                model=self.model,
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": _LURE_SCHEMA},
                },
                messages=[{"role": "user", "content": prompt}],
            )
            if response.stop_reason == "refusal":
                raise LureGenerationError(
                    f"LLM declined the lure-copy request for brand={brand_display!r}: "
                    f"{getattr(response.stop_details, 'explanation', None)}"
                )
            text = next(block.text for block in response.content if block.type == "text")
            data = json.loads(text)
            lure = LureCopy(title=data["title"], lure_copy=data["lure_copy"])
            if _looks_like_refusal(lure):
                raise LureGenerationError(
                    f"model refused inside schema-valid JSON for brand={brand_display!r}, "
                    f"tone={tone!r}: {lure.title!r} / {lure.lure_copy!r}"
                )
            return text, lure

        (raw_text, lure), attempt = _with_retries(
            _call, f"generate_lure({brand_display!r}, {tone!r}) [anthropic]", self._max_retries
        )
        _append_manifest(
            self._manifest_path, "anthropic", self.model, brand_display, tone, prompt, raw_text, attempt
        )
        return lure


class GeminiLureClient:
    """Thin wrapper around the Gemini API (`google-genai`) for lure-copy
    generation.

    Constructing this requires the `google-genai` package (`pip install -e
    ".[gemini]"`) and an API key resolved by the SDK's default client
    (`GEMINI_API_KEY` or `GOOGLE_API_KEY` env var — get a free-tier key at
    https://aistudio.google.com/apikey).
    """

    def __init__(
        self,
        model: str = GEMINI_DEFAULT_MODEL,
        effort: Optional[str] = None,
        manifest_path: Path = DEFAULT_MANIFEST_PATH,
        max_retries: int = DEFAULT_MAX_RETRIES,
        min_call_interval: float = 4.5,
    ):
        from google import genai  # deferred: only required in --live mode

        self._genai = genai
        self._client = genai.Client()
        self.model = model
        self.effort = effort  # accepted for CLI symmetry with Anthropic; unused by Gemini
        self._manifest_path = Path(manifest_path)
        self._max_retries = max_retries
        # Free-tier flash models cap at 15 req/min/project/model — self-pace
        # rather than only reacting after a 429, since a burst of calls (the
        # normal shape of this workload) hits that ceiling within seconds.
        self._min_call_interval = min_call_interval
        self._last_call_at: Optional[float] = None

    def generate_lure(self, brand_display: str, tone: str) -> LureCopy:
        from google.genai import types

        prompt = _build_prompt(brand_display, tone)

        def _call():
            if self._last_call_at is not None:
                elapsed = time.monotonic() - self._last_call_at
                wait = self._min_call_interval - elapsed
                if wait > 0:
                    time.sleep(wait)
            self._last_call_at = time.monotonic()
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=_GEMINI_LURE_SCHEMA,
                ),
            )
            if not response.text:
                raise LureGenerationError(
                    f"Gemini returned no content for brand={brand_display!r} "
                    f"(possibly blocked — check response.prompt_feedback)"
                )
            data = json.loads(response.text)
            lure = LureCopy(title=data["title"], lure_copy=data["lure_copy"])
            if _looks_like_refusal(lure):
                raise LureGenerationError(
                    f"model refused inside schema-valid JSON for brand={brand_display!r}, "
                    f"tone={tone!r}: {lure.title!r} / {lure.lure_copy!r}"
                )
            return response.text, lure

        (raw_text, lure), attempt = _with_retries(
            _call, f"generate_lure({brand_display!r}, {tone!r}) [gemini]", self._max_retries
        )
        _append_manifest(
            self._manifest_path, "gemini", self.model, brand_display, tone, prompt, raw_text, attempt
        )
        return lure


def build_lure_client(provider: str, model: str, effort: str):
    """Construct the lure client for `provider` ("anthropic" | "gemini")."""
    if provider == "anthropic":
        return AnthropicLureClient(model=model, effort=effort)
    if provider == "gemini":
        return GeminiLureClient(model=model, effort=effort)
    raise ValueError(f"unknown provider: {provider!r} (expected 'anthropic' or 'gemini')")
