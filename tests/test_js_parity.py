"""Cross-runtime parity test: runs the ACTUAL extension/page_extractor.js
source (via Node + jsdom, see tests_js/extract_features.mjs) against the
same fixtures/URLs used elsewhere in this suite, and asserts its output
matches Python's real extract_features() key-for-key.

This is the automated version of FEATURE_PARITY.md's table -- that
document was hand-verified by direct code comparison; this test proves
it by actually running both implementations on identical input, so
future edits to either side that break parity fail CI instead of only
being caught by re-reading the table.

Skipped gracefully (not failed) if Node/jsdom aren't set up, matching
this project's existing pattern for other infra-dependent tests (see
tests/live/). To set up: `cd tests_js && npm install` (needs Node on
PATH -- see LOCAL_SETUP.md for how this project's dev environment
obtained one, since it isn't preinstalled everywhere).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from phishshield.data.schema import Sample, Source
from phishshield.features.pipeline import extract_features

REPO_ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
JS_RUNNER = REPO_ROOT / "tests_js" / "extract_features.mjs"
NODE_MODULES = REPO_ROOT / "tests_js" / "node_modules"

_NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(
    _NODE is None or not NODE_MODULES.exists(),
    reason="Node.js and/or tests_js/node_modules (jsdom) not set up -- see this file's docstring",
)

# (fixture path or None for a bare html document, url) pairs -- reused
# from the same fixtures/URLs already exercised in test_model_store.py
# and test_api.py so this test targets known, already-meaningful cases
# rather than inventing new ones.
CASES = [
    ("phishing_paypal_clone.html", "https://paypa1-secure.tk/login"),
    ("benign_example.html", "https://example.com/"),
    (None, "https://en.wikipedia.org/wiki/Phishing"),
    (None, "https://www.google.com"),
    (None, "http://192.168.1.1/login"),  # IPv4 literal
    (None, "http://[2001:db8::1]/login"),  # IPv6 literal -- see FEATURE_PARITY.md's
    # has_ip_literal note: Python uses stdlib `ipaddress`, JS uses a regex
    # approximation. This case and test_js_extractor_matches_python_for_ip_literal_url
    # both confirm they agree for standard notation; not exhaustive for every
    # valid-but-unusual IPv6 textual form.
]


# The exact HTML page_extractor.js's Node harness feeds jsdom when no
# fixture file is given (see extract_features.mjs's default for "-").
# Kept in sync here deliberately: passing this same string to Python's
# extract_features() is what makes the "no local fixture" cases a fair
# comparison (both sides then have has_html=1 with the same empty-body
# structure), rather than comparing JS's always-has_html=1-for-a-live-tab
# reality against Python's has_html=0-for-no-html-string case, which are
# two different scenarios, not a parity bug.
_BARE_HTML = "<!DOCTYPE html><html><head></head><body></body></html>"


def _run_js_extractor(html_path: str | None, url: str) -> dict:
    html_arg = str(FIXTURES / html_path) if html_path else "-"
    result = subprocess.run(
        [_NODE, str(JS_RUNNER), html_arg, url],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    data = json.loads(result.stdout)
    # _meta_url is location.href as jsdom (WHATWG URL spec, same as a
    # real browser) normalized it -- e.g. adds a trailing "/" to a bare
    # domain. Using this exact string for the Python-side comparison
    # means both sides are scored on the identical final URL a real
    # browser tab would actually report, not a raw un-normalized input.
    normalized_url = data.pop("_meta_url")
    data.pop("_meta_title", None)
    return data, normalized_url


def _python_features(html_path: str | None, url: str, label: int = 0) -> dict:
    html = (FIXTURES / html_path).read_text() if html_path else _BARE_HTML
    sample = Sample(url=url, label=label, source=Source.TRANCO, html=html)
    return extract_features(sample)


@pytest.mark.parametrize("html_path,url", CASES)
def test_js_extractor_matches_python_pipeline(html_path, url):
    js_features, normalized_url = _run_js_extractor(html_path, url)
    py_features = _python_features(html_path, normalized_url)

    assert set(js_features.keys()) == set(py_features.keys()), (
        f"feature key sets differ: JS-only={set(js_features) - set(py_features)}, "
        f"Python-only={set(py_features) - set(js_features)}"
    )
    mismatches = {}
    for key in py_features:
        js_val, py_val = js_features[key], py_features[key]
        if isinstance(py_val, float) or isinstance(js_val, float):
            if abs(float(js_val) - float(py_val)) > 1e-9:
                mismatches[key] = (js_val, py_val)
        elif js_val != py_val:
            mismatches[key] = (js_val, py_val)

    assert not mismatches, f"JS vs Python feature mismatch for url={url!r}: {mismatches}"


def test_js_extractor_matches_python_for_ip_literal_url():
    # Targeted regression test for FEATURE_PARITY.md's flagged
    # has_ip_literal approximation gap (Python's stdlib `ipaddress` vs.
    # JS's regex heuristic) -- proves whether it's a real mismatch or a
    # documented-but-harmless difference, rather than leaving it as an
    # untested claim.
    url = "http://192.168.1.1/login"
    js_features, normalized_url = _run_js_extractor(None, url)
    py_features = _python_features(None, normalized_url)
    assert js_features["has_ip_literal"] == py_features["has_ip_literal"] == 1
