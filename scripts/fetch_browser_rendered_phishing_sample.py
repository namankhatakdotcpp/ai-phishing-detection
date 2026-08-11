"""Task 2 (diagnostic only, does not feed v4 training): a larger
static-vs-browser comparison on the phishing side than Section 3.12's
n=2 manual check, to see whether that finding holds at scale.

Samples N rows from data/generated/llm_phishing_v1.jsonl (already-saved
HTML, label=1), serves each locally, renders in real Chromium, and
extracts features via the real page_extractor.js -- compared against
the existing Python-extracted static features for the same HTML
(computed fresh here, not reusing any cached older run).

This does NOT feed the v4 training set. Its only purpose is to check
whether Section 3.12's "phishing doesn't need re-rendering" finding
generalizes beyond 2 samples, per the explicit instruction not to claim
that from too small an n.

Usage:
    python scripts/fetch_browser_rendered_phishing_sample.py [N]
"""

from __future__ import annotations

import json
import random
import sys
import threading
import warnings
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from bs4 import XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from phishshield.features.html_features import extract_html_features  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR_PATH = REPO_ROOT / "extension" / "page_extractor.js"
OUT_PATH = REPO_ROOT / "data" / "evaluation" / "browser_rendered_phishing_sample.jsonl"
PORT = 8972
SEED = 42
N_DEFAULT = 20

STAGE_DIR = REPO_ROOT / "tests" / "fixtures" / "_staged_phishing_sample"


def start_server(directory: Path) -> HTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = HTTPServer(("127.0.0.1", PORT), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main() -> None:
    from playwright.sync_api import sync_playwright

    n = int(sys.argv[1]) if len(sys.argv) > 1 else N_DEFAULT
    with open(REPO_ROOT / "data" / "generated" / "llm_phishing_v1.jsonl") as f:
        rows = [json.loads(line) for line in f]
    random.Random(SEED).shuffle(rows)
    sample = rows[:n]

    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    for i, row in enumerate(sample):
        (STAGE_DIR / f"{i}.html").write_text(row["html"])

    server = start_server(STAGE_DIR)
    extractor_source = EXTRACTOR_PATH.read_text()
    results = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1366, "height": 900})
            for i, row in enumerate(sample):
                static_feats = extract_html_features(row["html"], row["url"])
                page = context.new_page()
                page.goto(f"http://127.0.0.1:{PORT}/{i}.html", wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(500)
                live_feats = page.evaluate(extractor_source)
                page.close()
                results.append({"url": row["url"], "static": static_feats, "live": live_feats})
            context.close()
            browser.close()
    finally:
        for f in STAGE_DIR.glob("*.html"):
            f.unlink()
        STAGE_DIR.rmdir()
        server.shutdown()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for row in results:
            f.write(json.dumps(row) + "\n")

    cols = ["num_iframes", "num_hidden_elements", "num_external_js_domains", "num_password_fields"]
    n_changed = 0
    for c in cols:
        deltas = []
        for r in results:
            sv = r["static"].get(c, 0)
            lv = r["live"].get(c, 0)
            deltas.append(lv - sv)
        changed = sum(1 for d in deltas if d != 0)
        n_changed += changed
        print(f"{c:28s} n_changed={changed}/{len(results)}  mean_delta={sum(deltas)/len(deltas):+.3f}  max_delta={max(deltas):+d}")
    print(f"\n{n} phishing samples compared -> {OUT_PATH}")
    print(f"total (sample, feature) pairs with any static-vs-live difference: {n_changed}/{n*len(cols)}")


if __name__ == "__main__":
    main()
