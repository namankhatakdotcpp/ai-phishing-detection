"""Fetch real HTML for a curated hard-negative benign evaluation set:
major services, developer/docs sites, news, universities, banks, and
a few realistic subpages (not just homepages) -- see
reports/FINAL_REPORT.md Section 3.6/3.7 for why this exists (real
false positives found on major benign sites after earlier fixes).

This is an EVALUATION set, not automatically folded into training --
see scripts/eval_hard_negatives.py for scoring, and FINAL_REPORT.md for
what to do with the results before ever adding these to training data
(domain-disjoint from any training split, documented, not silently
mixed in).

Ethical note: same policy as fetch_tranco_html.py -- these are real,
legitimate, well-provisioned sites, safe to fetch (unlike live phishing
pages, which this project never fetches). Bot-blocked/rate-limited
responses are recorded and excluded from the evaluation set rather than
silently treated as representative benign HTML (a 403/429/timeout is
not a real sample of the site's structure).

Usage:
    python scripts/fetch_hard_negatives.py
"""

from __future__ import annotations

import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "tests_js" / "hard_negative_fixtures"
FETCH_LOG = REPO_ROOT / "data" / "evaluation" / "hard_negatives_fetch_log.txt"
UA = "PhishShield-AI/1.0 research (course project; hard-negative eval)"
TIMEOUT = 6.0

URLS = [
    ("google_home", "https://www.google.com/"),
    ("google_search", "https://www.google.com/search?q=phishing+detection"),
    ("youtube_home", "https://www.youtube.com/"),
    ("wikipedia_phishing", "https://en.wikipedia.org/wiki/Phishing"),
    ("wikipedia_python", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
    ("github_home", "https://github.com/"),
    ("github_repo", "https://github.com/torvalds/linux"),
    ("github_issues", "https://github.com/facebook/react/issues"),
    ("amazon_home", "https://www.amazon.com/"),
    ("microsoft_home", "https://www.microsoft.com/en-us"),
    ("apple_home", "https://www.apple.com/"),
    ("reddit_home", "https://www.reddit.com/"),
    ("linkedin_home", "https://www.linkedin.com/"),
    ("paypal_home", "https://www.paypal.com/"),
    ("netflix_home", "https://www.netflix.com/"),
    ("adobe_home", "https://www.adobe.com/"),
    ("dropbox_home", "https://www.dropbox.com/"),
    ("stackoverflow_home", "https://stackoverflow.com/"),
    ("stackoverflow_q", "https://stackoverflow.com/questions/tagged/python"),
    ("python_docs", "https://docs.python.org/3/"),
    ("mdn_home", "https://developer.mozilla.org/en-US/"),
    ("mdn_js", "https://developer.mozilla.org/en-US/docs/Web/JavaScript"),
    ("bbc_news", "https://www.bbc.com/news"),
    ("nytimes", "https://www.nytimes.com/"),
    ("cnn", "https://www.cnn.com/"),
    ("reuters", "https://www.reuters.com/"),
    ("mit", "https://www.mit.edu/"),
    ("stanford", "https://www.stanford.edu/"),
    ("iitb", "https://www.iitb.ac.in/"),
    ("iitd", "https://home.iitd.ac.in/"),
    ("harvard", "https://www.harvard.edu/"),
    ("wikipedia_org", "https://www.wikipedia.org/"),
    ("twitter_x", "https://twitter.com/"),
    ("instagram", "https://www.instagram.com/"),
    ("facebook", "https://www.facebook.com/"),
    ("spotify", "https://www.spotify.com/"),
    ("slack", "https://slack.com/"),
    ("zoom", "https://zoom.us/"),
    ("salesforce", "https://www.salesforce.com/"),
    ("atlassian", "https://www.atlassian.com/"),
    ("npmjs", "https://www.npmjs.com/"),
    ("pypi", "https://pypi.org/"),
    ("readthedocs", "https://readthedocs.org/"),
    ("medium", "https://medium.com/"),
    ("quora", "https://www.quora.com/"),
    ("ebay", "https://www.ebay.com/"),
    ("walmart", "https://www.walmart.com/"),
    ("target", "https://www.target.com/"),
    ("bestbuy", "https://www.bestbuy.com/"),
    ("chase_bank", "https://www.chase.com/"),
    ("bankofamerica", "https://www.bankofamerica.com/"),
    ("wellsfargo", "https://www.wellsfargo.com/"),
    ("coinbase", "https://www.coinbase.com/"),
    ("docusign", "https://www.docusign.com/"),
    ("outlook", "https://outlook.com/"),
    ("office", "https://www.office.com/"),
    ("icloud", "https://www.icloud.com/"),
    ("protonmail", "https://proton.me/mail"),
]


def fetch_one(name: str, url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            body = resp.read(500_000)
    except Exception as exc:
        return name, url, None, str(exc)[:80]
    return name, url, status, body


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FETCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(fetch_one, name, url): (name, url) for name, url in URLS}
        for i, fut in enumerate(as_completed(futures), 1):
            name, url, status, payload = fut.result()
            if status == 200 and isinstance(payload, (bytes, bytearray)):
                (OUT_DIR / f"{name}.html").write_bytes(payload)
                results.append((name, url, len(payload), "ok"))
            else:
                note = payload if isinstance(payload, str) else f"status={status}"
                results.append((name, url, 0, note))
            print(f"[{i}/{len(URLS)}] {name}: {results[-1][2]} bytes, {results[-1][3]}")

    with open(FETCH_LOG, "w") as f:
        for name, url, size, note in results:
            f.write(f"{name}|{url}|{size}|{note}\n")
    ok = sum(1 for r in results if r[3] == "ok")
    print(f"\n{ok}/{len(URLS)} fetched successfully. Log: {FETCH_LOG}")


if __name__ == "__main__":
    main()
