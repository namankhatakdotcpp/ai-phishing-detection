from pathlib import Path

from phishshield.data.loaders import load_openphish, load_phishtank, load_tranco, registrable_domain
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
    assert registrable_domain(samples[0].url) == "google"


def test_load_tranco_respects_limit():
    samples = load_tranco(FIXTURES / "tranco_sample.csv", limit=2)
    assert len(samples) == 2


def test_load_tranco_is_deterministic_given_seed():
    a = load_tranco(FIXTURES / "tranco_sample.csv", seed=7)
    b = load_tranco(FIXTURES / "tranco_sample.csv", seed=7)
    assert [s.url for s in a] == [s.url for s in b]


def test_load_tranco_produces_path_variety_not_bare_roots_only():
    # Regression test: load_tranco() previously always produced bare
    # domain roots (path_length=0 for every benign sample), which taught
    # the classifier "any URL path -> phishing" -- a real bug caught via
    # live-extension testing (see PROJECT_BRIEF.md, Phase 9 "path_length
    # artifact" entry). Across enough seeds, at least one non-root URL
    # must appear (only 3 fixture rows per seed, so pool many seeds).
    is_bare_root = lambda url: url == f"https://{url.split('/')[2]}"  # noqa: E731
    all_urls = [
        s.url
        for seed in range(20)
        for s in load_tranco(FIXTURES / "tranco_sample.csv", seed=seed)
    ]
    assert any(not is_bare_root(url) for url in all_urls)
    assert any(is_bare_root(url) for url in all_urls)  # bare root still possible


def test_load_tranco_produces_subdomain_variety_not_bare_apex_only():
    # Regression test: load_tranco() previously always produced bare apex
    # domains (num_subdomains=0 for every benign sample -- ~95% vs. 12-27%
    # for real phishing sources), which taught the classifier "any
    # subdomain -> phishing" -- caught via a live false positive on
    # en.wikipedia.org (see PROJECT_BRIEF.md, Phase 9). Across enough
    # seeds, both bare-apex and subdomained URLs must appear.
    all_domains = [
        s.url.split("//")[1].split("/")[0]
        for seed in range(20)
        for s in load_tranco(FIXTURES / "tranco_sample.csv", seed=seed)
    ]
    has_subdomain = lambda host: host.count(".") >= 2  # noqa: E731
    assert any(has_subdomain(h) for h in all_domains)
    assert any(not has_subdomain(h) for h in all_domains)
