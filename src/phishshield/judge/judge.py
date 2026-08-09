"""Mocked LLM-judge module: turns extracted structured features into a
structured risk explanation, matching the "Risk Score: 91% — reasons..."
format from the original pitch.

ETHICAL / SCOPE CONSTRAINT: this is a MOCK for the course deadline — it
does not call any real LLM API. It is a deterministic rule engine over the
same feature dict the Phase 1 pipeline already produces (never raw HTML,
per the project brief's "given extracted structured features, not raw
HTML" requirement). Swapping in a real LLM call later only requires
replacing `judge_features()`'s body with a prompt built from the same
feature dict, returning the same `JudgeVerdict` shape.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from phishshield.data.pipeline import feature_columns

Rule = tuple[Callable[[dict], bool], int, str]

# (predicate over a feature dict, weight added to risk score, human-readable reason)
_RULES: list[Rule] = [
    (
        lambda f: f.get("num_password_fields", 0) >= 1 and f.get("has_external_form_action", 0) == 1,
        30,
        "Login form submits credentials to a different domain than the one hosting the page.",
    ),
    (
        lambda f: f.get("title_brand_mismatch", 0) == 1,
        25,
        "Page title/branding references a company whose domain doesn't match the site's actual domain.",
    ),
    (
        lambda f: f.get("has_ip_literal", 0) == 1,
        20,
        "Site is hosted directly on a raw IP address instead of a registered domain name.",
    ),
    (
        lambda f: f.get("has_suspicious_tld", 0) == 1,
        15,
        "Domain uses a top-level domain commonly abused for throwaway phishing registrations.",
    ),
    (
        lambda f: f.get("has_at_symbol", 0) == 1,
        15,
        "URL contains an '@' symbol, a classic trick to hide the real destination host.",
    ),
    (
        lambda f: f.get("is_https", 1) == 0,
        10,
        "Connection is not secured with HTTPS.",
    ),
    (
        lambda f: f.get("num_subdomains", 0) >= 2,
        10,
        "Unusually long subdomain chain, often used to disguise the real domain.",
    ),
    (
        lambda f: f.get("num_external_js_domains", 0) >= 1,
        8,
        "Page loads JavaScript from an external, unrelated domain.",
    ),
    (
        lambda f: f.get("num_hidden_elements", 0) >= 1,
        7,
        "Page contains hidden elements, sometimes used to conceal tracking or malicious content.",
    ),
    (
        lambda f: f.get("special_char_ratio", 0.0) > 0.15,
        8,
        "URL has an unusually high ratio of special characters.",
    ),
]

_NO_FINDINGS_REASON = "No significant phishing indicators detected in structural features."

HIGH_RISK_THRESHOLD = 70
MEDIUM_RISK_THRESHOLD = 40


@dataclass(frozen=True)
class JudgeVerdict:
    risk_score: int  # 0-100
    risk_band: str  # "high" | "medium" | "low"
    reasons: list[str]


def _risk_band(risk_score: int) -> str:
    if risk_score >= HIGH_RISK_THRESHOLD:
        return "high"
    if risk_score >= MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"


def judge_features(features: dict) -> JudgeVerdict:
    """Score a single feature dict (as produced by
    `phishshield.features.pipeline.extract_features`) and explain why.
    """
    reasons = [reason for predicate, _, reason in _RULES if predicate(features)]
    raw_score = sum(weight for predicate, weight, _ in _RULES if predicate(features))
    risk_score = min(100, raw_score)

    if not reasons:
        reasons = [_NO_FINDINGS_REASON]

    return JudgeVerdict(risk_score=risk_score, risk_band=_risk_band(risk_score), reasons=reasons)


def judge_dataframe(df: pd.DataFrame, log: list[dict] | None = None) -> pd.Series:
    """Score every row of a feature dataframe. Returns a `judge_score`
    Series aligned to `df.index`, on a 0-1 scale so it's directly
    comparable to/fusable with classifier probabilities.

    If `log` is given (a list), one record per row is appended to it:
    `{"index": ..., "features": ..., "risk_score": ..., "risk_band": ...,
    "reasons": ...}` — the "prompt"/"response" pair for that row, in the
    sense a real LLM call would take `features` as its prompt input and
    return the verdict fields as its response. Pass the same list across
    multiple calls to build up one combined evaluation log; persist it
    with `save_judge_log`.
    """
    cols = feature_columns(df)
    scores = []
    for idx, row in df[cols].iterrows():
        features = row.to_dict()
        verdict = judge_features(features)
        scores.append(verdict.risk_score / 100)
        if log is not None:
            log.append({"index": idx, "features": features, **asdict(verdict)})

    return pd.Series(scores, index=df.index, name="judge_score")


def save_judge_log(log: list[dict], path: str | Path) -> None:
    """Persist a judge log (as built by `judge_dataframe`'s `log` param) as
    JSONL, one record per line, for Phase 5's reproducibility requirement:
    every feature-dict/verdict pair used during an evaluation run should be
    inspectable afterward.
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for record in log:
            f.write(json.dumps(record) + "\n")
