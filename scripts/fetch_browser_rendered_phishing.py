"""Section 3.11/3.12 phishing-side check: does real browser rendering
change phishing feature vectors the way it changed benign ones?

Real phishing URLs are deliberately not fetched live (this project's
stated ethical policy, see fetch_hard_negatives.py) -- instead this
serves this project's own controlled phishing fixtures
(tests/fixtures/phishing_paypal_clone.html, and a fresh sample from
data/generated/llm_phishing_v1.jsonl) over a local HTTP server, then
loads them in real Chromium and extracts features via the real
page_extractor.js, exactly like fetch_browser_rendered_features.py does
for the benign side. This is a same-methodology comparison, not a
second, different one.

Usage:
    python scripts/fetch_browser_rendered_phishing.py
"""

from __future__ import annotations

import json
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR_PATH = REPO_ROOT / "extension" / "page_extractor.js"
OUT_PATH = REPO_ROOT / "data" / "evaluation" / "browser_rendered_phishing.jsonl"
PORT = 8971

SAMPLES = [
    ("phishing_paypal_clone", "phishing_paypal_clone.html", "https://paypa1-secure.tk/login"),
]


def start_server(directory: Path) -> HTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = HTTPServer(("127.0.0.1", PORT), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main() -> None:
    extractor_source = EXTRACTOR_PATH.read_text()

    # Serve tests/fixtures/ for the hand-crafted fixture.
    fixtures_dir = REPO_ROOT / "tests" / "fixtures"
    server = start_server(fixtures_dir)

    # Also stage a fresh LLM-generated phishing sample next to it.
    with open(REPO_ROOT / "data" / "generated" / "llm_phishing_v1.jsonl") as f:
        llm_row = json.loads(f.readline())
    staged_path = fixtures_dir / "_staged_llm_phishing_sample.html"
    staged_path.write_text(llm_row["html"])

    results = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1366, "height": 900})

            for name, filename, canonical_url in SAMPLES:
                page = context.new_page()
                page.goto(f"http://127.0.0.1:{PORT}/{filename}", wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(1000)
                features = page.evaluate(extractor_source)
                results.append({"name": name, "canonical_url": canonical_url, "features": features})
                page.close()

            # The fresh LLM sample, served + rendered the same way.
            page = context.new_page()
            page.goto(
                f"http://127.0.0.1:{PORT}/_staged_llm_phishing_sample.html",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            page.wait_for_timeout(1000)
            features = page.evaluate(extractor_source)
            results.append({"name": "llm_phishing_sample", "canonical_url": llm_row["url"], "features": features})
            page.close()

            context.close()
            browser.close()
    finally:
        staged_path.unlink(missing_ok=True)
        server.shutdown()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for row in results:
            f.write(json.dumps(row) + "\n")
    print(f"wrote {len(results)} rows -> {OUT_PATH}")
    for row in results:
        print(row["name"], row["features"])


if __name__ == "__main__":
    main()
