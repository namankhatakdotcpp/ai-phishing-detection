from phishshield.features.url_features import extract_url_features


def test_benign_url_has_low_risk_signals():
    features = extract_url_features("https://example.com/")
    assert features["is_parsable"] == 1
    assert features["has_ip_literal"] == 0
    assert features["has_at_symbol"] == 0
    assert features["num_subdomains"] == 0
    assert features["is_https"] == 1
    assert features["has_suspicious_tld"] == 0


def test_phishing_shaped_url_trips_multiple_signals():
    url = "http://192.168.1.5@paypal-secure-login.verify-account.top/signin?redirect=x"
    features = extract_url_features(url)
    assert features["has_at_symbol"] == 1
    assert features["is_https"] == 0
    assert features["has_suspicious_tld"] == 1
    assert features["num_subdomains"] >= 1


def test_ip_literal_host_detected():
    features = extract_url_features("http://203.0.113.5/login")
    assert features["has_ip_literal"] == 1


def test_empty_url_does_not_crash():
    features = extract_url_features("")
    assert features["is_parsable"] == 0
    assert features["url_length"] == 0


def test_malformed_url_does_not_crash():
    features = extract_url_features("http://[::1:not-valid")
    assert features["is_parsable"] == 0
