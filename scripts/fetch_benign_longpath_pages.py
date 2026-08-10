"""Fetch real HTML for benign pages with long, realistic paths (wiki
articles, API docs, issue trackers) -- fixes a diagnosed training-data
gap: `path_length`/`url_length` on real documentation/wiki/issue pages
sit at the 92nd-100th percentile of the current has_html=1 benign
training population (n=91, dominated by homepages and short templated
paths), so the classifier treats "long path" as near-unconditional
evidence of phishing on pages like wikipedia_python, github_issues,
mdn_js (see reports/FINAL_REPORT.md Section 3.9).

IMPORTANT -- domain-disjoint from the hard-negative EVALUATION set
(data/evaluation/hard_negatives_fetch_log.txt): every domain used there
(including en.wikipedia.org, github.com, developer.mozilla.org) is
deliberately excluded here, so the evaluation set stays independent.

Usage:
    python scripts/fetch_benign_longpath_pages.py
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_JSONL = REPO_ROOT / "data" / "generated" / "benign_longpath_pages.jsonl"
FETCH_LOG = REPO_ROOT / "data" / "evaluation" / "benign_longpath_fetch_log.txt"
UA = "PhishShield-AI/1.0 research (course project; benign long-path training sample)"
TIMEOUT = 8.0
MAX_HTML_BYTES = 300_000
MIN_BYTES = 500

# Deliberately NOT overlapping any domain in data/evaluation/hard_negatives_fetch_log.txt
URLS = [
    ("wiktionary_article", "https://en.wiktionary.org/wiki/software"),
    ("wikibooks_article", "https://en.wikibooks.org/wiki/Python_Programming/Basic_Syntax"),
    ("wikimedia_docs", "https://www.mediawiki.org/wiki/Manual:Configuration_settings"),
    ("archwiki_article", "https://wiki.archlinux.org/title/Installation_guide"),
    ("gentoo_wiki", "https://wiki.gentoo.org/wiki/Handbook:AMD64"),
    ("debian_wiki", "https://wiki.debian.org/DebianPackage"),
    ("bugzilla_mozilla", "https://bugzilla.mozilla.org/buglist.cgi?bug_status=NEW"),
    ("pandas_docs", "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html"),
    ("numpy_docs", "https://numpy.org/doc/stable/reference/generated/numpy.array.html"),
    ("scikit_docs", "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html"),
    ("tensorflow_docs", "https://www.tensorflow.org/api_docs/python/tf/keras/layers/Dense"),
    ("pytorch_docs", "https://pytorch.org/docs/stable/generated/torch.nn.Linear.html"),
    ("docs_rs", "https://docs.rs/serde/latest/serde/trait.Serialize.html"),
    ("ruby_docs", "https://docs.ruby-lang.org/en/3.3/String.html"),
    ("oracle_docs", "https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/lang/String.html"),
    ("php_docs", "https://www.php.net/manual/en/function.array-merge.php"),
    ("postgresql_docs", "https://www.postgresql.org/docs/current/sql-select.html"),
    ("redis_docs", "https://redis.io/docs/latest/commands/set/"),
    ("elastic_docs", "https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html"),
    ("jenkins_docs", "https://www.jenkins.io/doc/book/pipeline/syntax/"),
    ("ansible_docs", "https://docs.ansible.com/ansible/latest/collections/ansible/builtin/copy_module.html"),
    ("terraform_docs", "https://developer.hashicorp.com/terraform/language/resources/syntax"),
    ("sourceforge_tracker", "https://sourceforge.net/p/sevenzip/discussion/45797/"),
    ("launchpad_bug", "https://bugs.launchpad.net/ubuntu/+bug/1999999"),
    ("codeberg_issues", "https://codeberg.org/forgejo/forgejo/issues"),
]


def fetch_one(name: str, url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            body = resp.read(MAX_HTML_BYTES)
    except Exception as exc:
        return name, url, None, str(exc)[:80]
    return name, url, status, body


def main() -> None:
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    FETCH_LOG.parent.mkdir(parents=True, exist_ok=True)

    results = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(fetch_one, name, url): (name, url) for name, url in URLS}
        for i, fut in enumerate(as_completed(futures), 1):
            name, url, status, payload = fut.result()
            if status == 200 and isinstance(payload, (bytes, bytearray)) and len(payload) >= MIN_BYTES:
                html = payload.decode("utf-8", errors="replace")
                results.append((name, url, len(payload), "ok", html))
            else:
                note = payload if isinstance(payload, str) else f"status={status}"
                results.append((name, url, 0, note, None))
            print(f"[{i}/{len(URLS)}] {name}: {results[-1][2]} bytes, {results[-1][3]}")

    kept = [r for r in results if r[3] == "ok"]
    with open(FETCH_LOG, "w") as f:
        for name, url, size, note, _html in results:
            f.write(f"{name}|{url}|{size}|{note}\n")

    with open(OUT_JSONL, "w") as f:
        for name, url, size, note, html in kept:
            f.write(json.dumps({"url": url, "label": 0, "source": "tranco", "html": html}) + "\n")

    print(f"\n{len(kept)}/{len(URLS)} usable. Wrote {OUT_JSONL}")


if __name__ == "__main__":
    main()
