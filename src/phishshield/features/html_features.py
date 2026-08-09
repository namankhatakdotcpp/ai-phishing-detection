"""Structural feature extraction from a page's HTML.

These features look only at static HTML/DOM structure — no headless
rendering, no visual/CNN similarity, no live JS execution (out of scope
for this research prototype; see project brief section 2).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from bs4 import BeautifulSoup

# Small fixed brand list for the title/body vs. domain mismatch heuristic.
# This is intentionally simple (exact substring match) — it is a weak
# signal meant to combine with other features, not a standalone detector.
_KNOWN_BRANDS = {
    "paypal", "amazon", "apple", "microsoft", "google", "chase",
    "wellsfargo", "bankofamerica", "netflix", "facebook", "instagram",
    "outlook", "office365", "dropbox", "linkedin", "coinbase",
}


def _registrable_domain(url: str) -> str:
    try:
        host = urlsplit(url if "://" in url else f"http://{url}").hostname or ""
    except ValueError:
        return ""
    parts = [p for p in host.lower().split(".") if p]
    if len(parts) < 2:
        return "".join(parts)
    return parts[-2]  # naive registrable label, e.g. "paypal" in paypal.com


def _external_domains(soup: BeautifulSoup, page_domain: str, tag: str, attr: str) -> set[str]:
    domains = set()
    for el in soup.find_all(tag):
        src = el.get(attr)
        if not src or not src.startswith(("http://", "https://", "//")):
            continue
        host = urlsplit(src if src.startswith("http") else f"http:{src}").hostname or ""
        parts = [p for p in host.lower().split(".") if p]
        domain = parts[-2] if len(parts) >= 2 else host.lower()
        if domain and domain != page_domain:
            domains.add(domain)
    return domains


def extract_html_features(html: str | None, url: str = "") -> dict:
    """Extract structural features from raw HTML.

    Returns a flat dict of numeric/boolean features. If `html` is None or
    empty, returns a zeroed vector with `has_html=0` so URL-only samples
    (e.g. benign Tranco entries without a fetched page) can still flow
    through the same pipeline.
    """
    features = {
        "has_html": 0,
        "num_forms": 0,
        "num_password_fields": 0,
        "num_text_input_fields": 0,
        "num_iframes": 0,
        "num_external_js_domains": 0,
        "num_external_form_actions": 0,
        "has_external_form_action": 0,
        "title_brand_mismatch": 0,
        "num_hidden_elements": 0,
        "has_favicon_mismatch": 0,
    }

    if not html or not html.strip():
        return features

    features["has_html"] = 1
    soup = BeautifulSoup(html, "lxml")
    page_domain = _registrable_domain(url)

    forms = soup.find_all("form")
    features["num_forms"] = len(forms)
    features["num_password_fields"] = len(soup.find_all("input", {"type": "password"}))
    features["num_text_input_fields"] = len(
        soup.find_all("input", {"type": ["text", "email"]})
    )
    features["num_iframes"] = len(soup.find_all("iframe"))

    features["num_external_js_domains"] = len(
        _external_domains(soup, page_domain, "script", "src")
    )

    external_actions = 0
    for form in forms:
        action = form.get("action") or ""
        if action.startswith(("http://", "https://")):
            action_host = urlsplit(action).hostname or ""
            action_domain = action_host.lower().split(".")[-2] if "." in action_host else action_host
            if page_domain and action_domain != page_domain:
                external_actions += 1
    features["num_external_form_actions"] = external_actions
    features["has_external_form_action"] = int(external_actions > 0)

    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    mentioned_brands = {b for b in _KNOWN_BRANDS if b in title}
    if mentioned_brands and page_domain not in mentioned_brands:
        features["title_brand_mismatch"] = 1

    hidden = soup.find_all(style=lambda v: v and "display:none" in v.replace(" ", "").lower())
    hidden += soup.find_all(style=lambda v: v and "visibility:hidden" in v.replace(" ", "").lower())
    features["num_hidden_elements"] = len(hidden)

    return features
