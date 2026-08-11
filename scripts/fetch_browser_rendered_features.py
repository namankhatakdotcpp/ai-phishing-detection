"""Section 3.11/3.12: real-browser (Playwright/Chromium) feature capture.

Every benign HTML source in this project before this script (Tranco,
login-page, long-path, and hard-negative fetchers) used a plain static
HTTP GET (`urllib.request.urlopen`) with zero JavaScript execution --
diagnosed in FINAL_REPORT.md Section 3.11 as the root cause of Finding 3
(Wells Fargo and other real, JS-heavy pages scoring HIGH live in Chrome
while scoring LOW against the same URL's statically-fetched feature
vector). This script captures the SAME curated URL set used by
scripts/fetch_hard_negatives.py, but through a real, headless Chromium
tab that waits for the network to settle before extraction -- as close
to what a real user's Chrome tab looks like when they click "Analyze"
as this project can get without an actual human driving Chrome.

Feature extraction is NOT reimplemented here. The real
extension/page_extractor.js source is read from disk and evaluated
in-page via Playwright's page.evaluate(), the same way
chrome.scripting.executeScript injects and evaluates it in the real
extension -- this is a parity requirement, not a convenience, so this
script can never define "hidden element" or "external JS domain"
differently from the extension.

This is an EVALUATION/diagnosis artifact. It does not retrain or modify
the deployed model. See FINAL_REPORT.md Section 3.11-3.12 for what to
do with the results.

Usage:
    python scripts/fetch_browser_rendered_features.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR_PATH = REPO_ROOT / "extension" / "page_extractor.js"
OUT_PATH = REPO_ROOT / "data" / "evaluation" / "browser_rendered_features.jsonl"
LOG_PATH = REPO_ROOT / "data" / "evaluation" / "browser_rendered_fetch_log.txt"

NAV_TIMEOUT_MS = 20000
SETTLE_WAIT_MS = 2500  # extra settle time after networkidle/load, for late ad/consent JS

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# A representative subset of scripts/fetch_hard_negatives.py's own URL
# list (same names, same URLs, so this is a direct, same-page
# static-vs-browser comparison, not a different sample) plus a few
# pages added specifically because they surfaced Finding 3 live
# (Section 3.10) and aren't in the original hard-negative set.
URLS = [
    # Home/search -- previously LOW both ways, included as a control.
    ("google_home", "https://www.google.com/"),
    ("wikipedia_org", "https://www.wikipedia.org/"),
    # JS-heavy consumer SPAs -- Section 3.10's Finding 3 pages.
    ("youtube_home", "https://www.youtube.com/"),
    ("youtube_watch", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("github_home", "https://github.com/"),
    ("github_repo", "https://github.com/torvalds/linux"),
    ("github_issues", "https://github.com/facebook/react/issues"),
    ("reddit_home", "https://www.reddit.com/"),
    ("instagram", "https://www.instagram.com/"),
    ("twitter_x", "https://twitter.com/"),
    # Banks -- the Wells Fargo diagnostic case, plus two more.
    ("wellsfargo", "https://www.wellsfargo.com/"),
    ("chase_bank", "https://www.chase.com/"),
    ("bankofamerica", "https://www.bankofamerica.com/"),
    # SaaS / login pages -- Section 3.8's original num_password_fields cases.
    ("salesforce_login", "https://login.salesforce.com/"),
    ("adobe_login", "https://auth.services.adobe.com/en_US/index.html"),
    ("dropbox_login", "https://www.dropbox.com/login"),
    ("slack_signin", "https://slack.com/signin"),
    ("zoom_signin", "https://zoom.us/signin"),
    ("wordpress_login", "https://wordpress.com/log-in"),
    ("stackoverflow_login", "https://stackoverflow.com/users/login"),
    ("google_accounts", "https://accounts.google.com/"),
    # Documentation / long-path pages -- Section 3.9's long-path cases.
    ("mdn_js", "https://developer.mozilla.org/en-US/docs/Web/JavaScript"),
    ("python_docs", "https://docs.python.org/3/"),
    ("react_docs", "https://react.dev/learn"),
    ("wikipedia_python", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
    # News -- typically ad/analytics-heavy, high num_external_js_domains.
    ("techcrunch", "https://techcrunch.com/"),
    ("theverge", "https://www.theverge.com/"),
    ("bbc_news", "https://www.bbc.com/news"),
    ("nytimes", "https://www.nytimes.com/"),
    # Universities.
    ("mit", "https://www.mit.edu/"),
    ("berkeley", "https://www.berkeley.edu/"),
    ("iitm", "https://www.iitm.ac.in/"),
]


def load_extractor_source() -> str:
    return EXTRACTOR_PATH.read_text()


def capture(playwright, name: str, url: str, extractor_source: str) -> dict:
    browser = playwright.chromium.launch(headless=True)
    try:
        context = browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900})
        page = context.new_page()
        started = time.time()
        try:
            page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="load")
            try:
                page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)
            except Exception:
                pass  # some sites never go idle (polling/analytics) -- fall through to the fixed settle wait
            page.wait_for_timeout(SETTLE_WAIT_MS)
            features = page.evaluate(extractor_source)
            return {
                "name": name,
                "url": url,
                "status": "ok",
                "elapsed_s": round(time.time() - started, 2),
                "features": features,
            }
        except Exception as exc:  # noqa: BLE001 -- recorded, not silently skipped
            return {
                "name": name,
                "url": url,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_s": round(time.time() - started, 2),
            }
        finally:
            context.close()
    finally:
        browser.close()


def main() -> None:
    extractor_source = load_extractor_source()
    results = []
    with sync_playwright() as playwright:
        for name, url in URLS:
            print(f"capturing {name} ({url}) ...", flush=True)
            result = capture(playwright, name, url, extractor_source)
            results.append(result)
            status = result["status"]
            print(f"  -> {status}" + (f": {result.get('error')}" if status == "error" else ""), flush=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for row in results:
            f.write(json.dumps(row) + "\n")

    with open(LOG_PATH, "w") as f:
        for row in results:
            f.write(f"{row['name']}|{row['url']}|{row['status']}|{row.get('error', 'ok')}\n")

    n_ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n{n_ok}/{len(results)} captured successfully -> {OUT_PATH}")


if __name__ == "__main__":
    main()
