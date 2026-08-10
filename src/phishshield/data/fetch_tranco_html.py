"""CLI entry point for fetching real HTML snapshots of top Tranco domains.

Why this exists: every real legacy loader (PhishTank/OpenPhish/Tranco) only
ever produces `html=None` samples (see `loaders.py` — no live network calls
there by design, since we do not fetch live phishing pages). That means the
classifier's training data has never contained a single real HTML example,
for either class, and any nonzero HTML-derived feature vector at eval time
is out-of-distribution rather than a learned "benign vs. phishing" signal.

Tranco domains are legitimate, well-provisioned, top-ranked sites, so
fetching their real front-page HTML is safe and ethical (unlike fetching
live phishing pages, which this project deliberately never does). This
gives the model real *benign* HTML examples to contrast against the
LLM-generated partition's phishing HTML.

Usage:
    python -m phishshield.data.fetch_tranco_html \\
        --tranco data/raw/tranco.csv --limit 300 \\
        --out data/generated/tranco_benign_html.jsonl
"""

from __future__ import annotations

import argparse
import socket
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from urllib.parse import urlsplit

from phishshield.data.generation import save_samples_jsonl
from phishshield.data.loaders import load_tranco

DEFAULT_OUT = "data/generated/tranco_benign_html.jsonl"
DEFAULT_LIMIT = 300
DEFAULT_WORKERS = 10
DEFAULT_TIMEOUT = 8.0
MAX_HTML_BYTES = 200_000
USER_AGENT = "PhishShield-AI/1.0 research (course project; benign-site HTML sample)"


def _fetch_html(url: str, timeout: float) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            body = resp.read(MAX_HTML_BYTES)
    except (urllib.error.URLError, socket.timeout, ValueError, ConnectionError, OSError):
        return None
    try:
        return body.decode("utf-8", errors="replace")
    except Exception:
        return None


def _fetch_one(sample):
    # `sample.url` now carries a load_tranco()-assigned realistic path (see
    # loaders.py) for feature-vector variety, but that fabricated path
    # almost certainly doesn't exist on the real site (404) -- fetch the
    # domain root instead, and attach the real HTML to the sample's actual
    # (possibly-pathed) URL. Both the URL shape and the HTML content are
    # genuinely benign either way; they just may not be the same physical
    # page, which doesn't matter for structural feature extraction.
    root = f"https://{urlsplit(sample.url).hostname}/"
    html = _fetch_html(root, DEFAULT_TIMEOUT)
    if html is None:
        html = _fetch_html(f"http://{urlsplit(sample.url).hostname}/", DEFAULT_TIMEOUT)
    return sample, html


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tranco", default="data/raw/tranco.csv")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="number of top-ranked domains to attempt")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()

    candidates = load_tranco(args.tranco, limit=args.limit)
    print(f"=== fetching HTML for {len(candidates)} top-ranked Tranco domains (workers={args.workers}) ===")

    fetched = []
    failures = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_fetch_one, s) for s in candidates]
        for i, future in enumerate(as_completed(futures), 1):
            sample, html = future.result()
            if html:
                fetched.append(replace(sample, html=html))
            else:
                failures += 1
            if i % 50 == 0 or i == len(candidates):
                print(f"  {i}/{len(candidates)} attempted, {len(fetched)} succeeded so far")

    save_samples_jsonl(fetched, args.out)
    print(f"wrote {len(fetched)} benign samples with real HTML to {args.out} ({failures} fetch failures)")


if __name__ == "__main__":
    main()
