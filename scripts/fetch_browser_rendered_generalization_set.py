"""Fixes Caveat A from the v3-vs-v4 evaluation: the original 130-page
hard-negative set shares 81% of its domains with v4's training data
(both were built from the same URL list), so scoring v4 against it is
not a fair generalization test.

This captures a SECOND, genuinely domain-disjoint benign set -- entirely
different domains from scripts/fetch_hard_negatives.py's list (and
therefore from v4's training data too) -- across the same categories
(banks, SaaS/login, docs, news, universities, e-commerce, dev sites).
NEVER used for training. Same capture method as
fetch_browser_rendered_benign.py (real Chromium, JS executed, DOM
serialized), same parallel-process approach.

Usage:
    python scripts/fetch_browser_rendered_generalization_set.py
"""

from __future__ import annotations

import json
import multiprocessing as mp
import re
from pathlib import Path

from fetch_browser_rendered_benign import _capture_one, EXTRACTOR_PATH, N_WORKERS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "generated" / "benign_generalization_set.jsonl"
MANIFEST_OUT = REPO_ROOT / "data" / "evaluation" / "benign_generalization_manifest.jsonl"

# Entirely different domains from scripts/fetch_hard_negatives.py's list
# (checked programmatically, not just by eye -- see the report for the
# disjointness verification).
URLS = [
    # Banks
    ("usbank", "https://www.usbank.com/"),
    ("pnc", "https://www.pnc.com/"),
    ("capitalone", "https://www.capitalone.com/"),
    ("ally_bank", "https://www.ally.com/"),
    ("hsbc_uk", "https://www.hsbc.co.uk/"),
    # SaaS / login pages
    ("monday", "https://monday.com/"),
    ("zendesk", "https://www.zendesk.com/"),
    ("hubspot", "https://www.hubspot.com/"),
    ("mailchimp_login", "https://login.mailchimp.com/"),
    ("box_login", "https://account.box.com/login"),
    ("okta_login", "https://login.okta.com/"),
    ("twilio_login", "https://login.twilio.com/"),
    # Documentation / dev sites
    ("vuejs_docs", "https://vuejs.org/guide/introduction.html"),
    ("angular_docs", "https://angular.dev/overview"),
    ("svelte_docs", "https://svelte.dev/docs"),
    ("tailwind_docs", "https://tailwindcss.com/docs/installation"),
    ("sourceforge", "https://sourceforge.net/"),
    ("launchpad", "https://launchpad.net/"),
    # News
    ("theatlantic", "https://www.theatlantic.com/"),
    ("vox", "https://www.vox.com/"),
    ("axios", "https://www.axios.com/"),
    ("engadget", "https://www.engadget.com/"),
    # Universities
    ("princeton", "https://www.princeton.edu/"),
    ("yale", "https://www.yale.edu/"),
    ("ucla", "https://www.ucla.edu/"),
    ("umich", "https://www.umich.edu/"),
    # E-commerce
    ("newegg", "https://www.newegg.com/"),
    ("wayfair", "https://www.wayfair.com/"),
    ("chewy", "https://www.chewy.com/"),
    # Long-path / wiki / subdomain-heavy
    ("wiktionary", "https://en.wiktionary.org/wiki/phishing"),
    ("archwiki", "https://wiki.archlinux.org/title/Installation_guide"),
    ("jsfiddle", "https://jsfiddle.net/"),
]

INTERSTITIAL_URL_PATTERNS = [
    r"js_challenge", r"/blocked\?", r"captcha", r"cf-browser-verification",
    r"access.denied", r"/sorry/", r"perimeterx", r"distil_r_captcha", r"incapsula",
]
INTERSTITIAL_TITLE_PATTERNS = [
    r"just a moment", r"are you a human", r"access denied", r"attention required",
    r"checking your browser", r"robot check", r"please verify", r"unusual traffic",
    r"robot or human",
]


def is_interstitial(url: str, title: str) -> bool:
    u = (url or "").lower()
    if any(re.search(p, u) for p in INTERSTITIAL_URL_PATTERNS):
        return True
    t = (title or "").lower()
    return any(re.search(p, t) for p in INTERSTITIAL_TITLE_PATTERNS)


def main() -> None:
    extractor_source = EXTRACTOR_PATH.read_text()
    jobs = [(name, url, extractor_source) for name, url in URLS]

    with mp.Pool(processes=N_WORKERS) as pool:
        results = list(pool.imap_unordered(_capture_one, jobs))

    n_ok = n_interstitial = n_error = 0
    with open(OUT_PATH, "w") as f_out, open(MANIFEST_OUT, "w") as f_manifest:
        for result in results:
            if result["status"] != "ok":
                n_error += 1
                f_manifest.write(json.dumps({k: v for k, v in result.items() if k != "html"}) + "\n")
                continue
            title = (result.get("js_features") or {}).get("_meta_title", "")
            if is_interstitial(result["final_url"], title):
                n_interstitial += 1
                f_manifest.write(json.dumps({**{k: v for k, v in result.items() if k != "html"}, "excluded_reason": "interstitial"}) + "\n")
                continue
            f_out.write(json.dumps({"url": result["final_url"], "label": 0, "source": "tranco", "html": result["html"]}) + "\n")
            f_manifest.write(json.dumps({k: v for k, v in result.items() if k != "html"}) + "\n")
            n_ok += 1

    print(f"ok+kept: {n_ok}, interstitial-excluded: {n_interstitial}, error: {n_error}, total: {len(URLS)}")
    print(f"-> {OUT_PATH}")


if __name__ == "__main__":
    main()
