from pathlib import Path

from phishshield.data.loaders import load_openphish, load_phishtank, load_tranco
from phishshield.data.schema import Source

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_phishtank():
    samples = load_phishtank(FIXTURES / "phishtank_sample.csv")
    assert len(samples) == 2
    assert all(s.label == 1 for s in samples)
    assert all(s.source == Source.PHISHTANK for s in samples)
    assert samples[0].url == "https://paypal-secure-login.verify-account.xyz/login"


def test_load_openphish():
    samples = load_openphish(FIXTURES / "openphish_sample.txt")
    assert len(samples) == 2
    assert all(s.label == 1 for s in samples)
    assert all(s.source == Source.OPENPHISH for s in samples)


def test_load_tranco():
    samples = load_tranco(FIXTURES / "tranco_sample.csv")
    assert len(samples) == 3
    assert all(s.label == 0 for s in samples)
    assert all(s.source == Source.TRANCO for s in samples)
    assert samples[0].url == "https://google.com"


def test_load_tranco_respects_limit():
    samples = load_tranco(FIXTURES / "tranco_sample.csv", limit=2)
    assert len(samples) == 2
