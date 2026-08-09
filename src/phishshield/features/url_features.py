"""Lexical feature extraction from a raw URL string.

These features look only at the URL text itself — no network calls (no
live WHOIS/SSL/DNS lookups, per the project's research-prototype scope).
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

_SPECIAL_CHARS = set("~!@#$%^&*()_+={}[]|\\:;\"'<>,?")
_SUSPICIOUS_TLDS = {
    "zip", "mov", "top", "xyz", "click", "gq", "tk", "ml", "cf", "ga",
}


def _is_ip_literal(host: str) -> bool:
    host = host.strip("[]")
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _registrable_parts(host: str) -> list[str]:
    return [p for p in host.split(".") if p]


def extract_url_features(url: str) -> dict:
    """Extract lexical/structural features from a URL.

    Returns a flat dict of numeric/boolean features suitable for a
    dataframe row. Never raises on malformed input — unparsable URLs
    yield a feature vector with `is_parsable=0` and zeroed-out fields
    rather than crashing the pipeline.
    """
    features = {
        "url_length": 0,
        "num_dots": 0,
        "num_hyphens": 0,
        "num_subdomains": 0,
        "num_digits": 0,
        "digit_ratio": 0.0,
        "special_char_count": 0,
        "special_char_ratio": 0.0,
        "has_at_symbol": 0,
        "has_ip_literal": 0,
        "is_https": 0,
        "path_length": 0,
        "query_length": 0,
        "has_suspicious_tld": 0,
        "has_port": 0,
        "is_parsable": 1,
    }

    url = (url or "").strip()
    features["url_length"] = len(url)
    if not url:
        features["is_parsable"] = 0
        return features

    try:
        parts = urlsplit(url if "://" in url else f"http://{url}")
    except ValueError:
        features["is_parsable"] = 0
        return features

    host = parts.hostname or ""
    features["num_dots"] = url.count(".")
    features["num_hyphens"] = url.count("-")
    features["has_at_symbol"] = int("@" in url)
    features["is_https"] = int(parts.scheme == "https")
    features["path_length"] = len(parts.path or "")
    features["query_length"] = len(parts.query or "")
    features["has_port"] = int(parts.port is not None)

    digits = sum(c.isdigit() for c in url)
    features["num_digits"] = digits
    features["digit_ratio"] = digits / len(url) if url else 0.0

    special = sum(c in _SPECIAL_CHARS for c in url)
    features["special_char_count"] = special
    features["special_char_ratio"] = special / len(url) if url else 0.0

    if host:
        features["has_ip_literal"] = int(_is_ip_literal(host))
        host_parts = _registrable_parts(host)
        # subdomain count = labels before the registrable domain (naive:
        # treat the last two labels as domain+TLD, everything before as subdomains)
        features["num_subdomains"] = max(0, len(host_parts) - 2)
        tld = host_parts[-1].lower() if host_parts else ""
        features["has_suspicious_tld"] = int(tld in _SUSPICIOUS_TLDS)

    return features
