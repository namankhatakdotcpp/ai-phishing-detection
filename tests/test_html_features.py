from pathlib import Path

from phishshield.features.html_features import extract_html_features

FIXTURES = Path(__file__).parent / "fixtures"


def test_empty_html_returns_zeroed_vector():
    features = extract_html_features(None, "https://example.com")
    assert features["has_html"] == 0
    assert features["num_forms"] == 0
    assert features["title_brand_mismatch"] == 0


def test_benign_page_has_no_phishing_signals():
    html = (FIXTURES / "benign_example.html").read_text()
    features = extract_html_features(html, "https://example.com/")
    assert features["has_html"] == 1
    assert features["num_forms"] == 0
    assert features["num_password_fields"] == 0
    assert features["title_brand_mismatch"] == 0
    assert features["has_external_form_action"] == 0


def test_phishing_clone_trips_multiple_signals():
    html = (FIXTURES / "phishing_paypal_clone.html").read_text()
    url = "https://paypal-secure-login.verify-account.xyz/login"
    features = extract_html_features(html, url)

    assert features["has_html"] == 1
    assert features["num_forms"] == 1
    assert features["num_password_fields"] == 1
    assert features["num_iframes"] == 1
    assert features["num_external_js_domains"] == 1
    assert features["num_hidden_elements"] == 1
    assert features["has_external_form_action"] == 1
    assert features["num_external_form_actions"] == 1


def test_title_brand_mismatch_flagged_when_domain_differs():
    html = (FIXTURES / "phishing_paypal_clone.html").read_text()
    # hosted on a domain that is NOT paypal.com -> title says PayPal, domain doesn't match
    features = extract_html_features(html, "https://totally-not-paypal.example/login")
    assert features["title_brand_mismatch"] == 1


def test_title_brand_mismatch_not_flagged_on_real_domain():
    html = (FIXTURES / "phishing_paypal_clone.html").read_text()
    features = extract_html_features(html, "https://paypal.com/login")
    assert features["title_brand_mismatch"] == 0
