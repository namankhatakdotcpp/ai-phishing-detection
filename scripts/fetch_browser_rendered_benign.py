"""Section 3.12 -> v4: build the canonical browser-rendered benign dataset.

Diagnosis (FINAL_REPORT.md Sections 3.11-3.12) established that every
prior benign HTML source in this project used a static, non-JS-executing
fetch, systematically undercounting num_iframes/num_hidden_elements/
num_external_js_domains/num_password_fields relative to what a real
Chrome tab sends. This script replaces that capture method for the
benign side: real Chromium (Playwright), JS fully executed, networkidle
settled, THEN the fully-rendered DOM is serialized (`page.content()`).

Design choice, and why it's not a second feature-extraction path: this
script does NOT hand off pre-extracted feature dicts to the training
pipeline. It saves the rendered HTML snapshot and lets the existing,
single Python extractor (phishshield.features.html_features /
url_features, via build_feature_dataframe) parse it exactly like every
other benign HTML source in this project. Since the DOM was already
fully hydrated by real JS before serialization, elements/scripts/iframes
that only existed after JS execution are present as literal markup in
the snapshot -- BeautifulSoup finds them the same way a live
`page_extractor.js` would in the browser. This keeps one feature
implementation, changes only what HTML goes into it.

A `page_extractor.js`-evaluated feature vector is ALSO recorded per page
(matching the diagnostic scripts) purely for direct comparison against
the Python-parsed features from the same snapshot -- a parity check on
this new pipeline, not a second training input.

Output schema matches `load_llm_generated()` (schema-generic loader,
already used for benign_login_pages.jsonl/benign_longpath_pages.jsonl):
{"url", "label": 0, "source": "tranco", "html"}.

URLs are the SAME curated list as scripts/fetch_hard_negatives.py
(imported directly, not copy-pasted, so the two can never silently
drift), split deterministically into a training pool and a
domain-disjoint held-out generalization set (every 5th entry by sorted
name -> held-out, ~20%) -- see FINAL_REPORT.md Section 3.13 Task 7.

Runs pages in parallel across worker processes (Playwright's sync API is
not safe to share across threads; separate processes sidestep that
rather than risking flaky shared-driver state).

Usage:
    python scripts/fetch_browser_rendered_benign.py
"""

from __future__ import annotations

import importlib.util
import json
import multiprocessing as mp
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR_PATH = REPO_ROOT / "extension" / "page_extractor.js"
HTML_OUT = REPO_ROOT / "data" / "generated" / "benign_browser_rendered.jsonl"
HELDOUT_OUT = REPO_ROOT / "data" / "generated" / "benign_browser_rendered_heldout.jsonl"
MANIFEST_OUT = REPO_ROOT / "data" / "evaluation" / "browser_rendered_benign_manifest.jsonl"
SPLIT_OUT = REPO_ROOT / "data" / "evaluation" / "browser_rendered_benign_split.json"

NAV_TIMEOUT_MS = 20000
SETTLE_WAIT_MS = 1500
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
N_WORKERS = 6


def _load_url_list() -> list[tuple[str, str]]:
    spec = importlib.util.spec_from_file_location("fetch_hard_negatives", REPO_ROOT / "scripts" / "fetch_hard_negatives.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.URLS


def _split(urls: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    ordered = sorted(urls, key=lambda t: t[0])
    heldout = [t for i, t in enumerate(ordered) if i % 5 == 4]
    train_pool = [t for i, t in enumerate(ordered) if i % 5 != 4]
    return train_pool, heldout


def _capture_one(args: tuple[str, str, str]) -> dict:
    name, url, extractor_source = args
    from playwright.sync_api import sync_playwright  # imported per-process

    started = time.time()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900})
                page = context.new_page()
                page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="load")
                try:
                    page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)
                except Exception:
                    pass
                page.wait_for_timeout(SETTLE_WAIT_MS)
                final_url = page.url
                html = page.content()
                try:
                    js_features = page.evaluate(extractor_source)
                except Exception as exc:  # noqa: BLE001
                    js_features = {"_error": f"{type(exc).__name__}: {exc}"}
                return {
                    "name": name,
                    "url": url,
                    "final_url": final_url,
                    "status": "ok",
                    "elapsed_s": round(time.time() - started, 2),
                    "html_len": len(html),
                    "html": html,
                    "js_features": js_features,
                    "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 -- recorded, never silently dropped
        return {
            "name": name,
            "url": url,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_s": round(time.time() - started, 2),
        }


def main() -> None:
    extractor_source = EXTRACTOR_PATH.read_text()
    all_urls = _load_url_list()
    train_pool, heldout = _split(all_urls)

    SPLIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(SPLIT_OUT, "w") as f:
        json.dump(
            {
                "total_urls": len(all_urls),
                "train_pool_n": len(train_pool),
                "heldout_n": len(heldout),
                "train_pool_names": [n for n, _ in train_pool],
                "heldout_names": [n for n, _ in heldout],
                "split_method": "deterministic, every 5th entry (sorted by name) -> heldout, ~20%",
            },
            f,
            indent=2,
        )

    print(f"total URLs: {len(all_urls)} | train pool: {len(train_pool)} | held-out: {len(heldout)}")

    jobs = [(name, url, extractor_source) for name, url in all_urls]
    results_by_name: dict[str, dict] = {}
    with mp.Pool(processes=N_WORKERS) as pool:
        for i, result in enumerate(pool.imap_unordered(_capture_one, jobs), start=1):
            results_by_name[result["name"]] = result
            status = result["status"]
            print(f"[{i}/{len(jobs)}] {result['name']}: {status}" + (f" ({result.get('error')})" if status == "error" else ""), flush=True)

    heldout_names = {n for n, _ in heldout}
    train_names = {n for n, _ in train_pool}

    with open(HTML_OUT, "w") as f_train, open(HELDOUT_OUT, "w") as f_heldout, open(MANIFEST_OUT, "w") as f_manifest:
        n_train_ok = n_heldout_ok = 0
        for name, url in all_urls:
            result = results_by_name.get(name, {"name": name, "url": url, "status": "missing"})
            f_manifest.write(json.dumps({k: v for k, v in result.items() if k != "html"}) + "\n")
            if result["status"] != "ok":
                continue
            record = {"url": result["final_url"], "label": 0, "source": "tranco", "html": result["html"]}
            if name in heldout_names:
                f_heldout.write(json.dumps(record) + "\n")
                n_heldout_ok += 1
            elif name in train_names:
                f_train.write(json.dumps(record) + "\n")
                n_train_ok += 1

    print(f"\ntrain benign captured: {n_train_ok}/{len(train_pool)} -> {HTML_OUT}")
    print(f"held-out benign captured: {n_heldout_ok}/{len(heldout)} -> {HELDOUT_OUT}")
    print(f"manifest (incl. failures, no HTML): {MANIFEST_OUT}")


if __name__ == "__main__":
    main()
