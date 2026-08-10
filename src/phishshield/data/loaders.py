"""Loaders that normalize raw dataset snapshots into `Sample` objects.

All loaders read local files only (no live network calls) — snapshots are
expected to already be downloaded into `data/raw/` (see the project brief,
Phase 1 acceptance criteria). Fetching those snapshots is a separate concern
from this module.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from urllib.parse import urlsplit

from phishshield.data.schema import Sample, Source


def registrable_domain(url: str) -> str:
    """Naive registrable-domain label (e.g. "google" for "www.google.com"),
    ignoring subdomain and path. Used to match a domain across differently
    -shaped URLs for the same site -- e.g. a plain `load_tranco()` entry
    (which may carry a random subdomain/path, see below) against a
    `fetch_tranco_html.py` entry for the same underlying domain.
    """
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""
    parts = [p for p in host.split(".") if p]
    if len(parts) < 2:
        return "".join(parts)
    return parts[-2]

# Realistic benign subpage shapes (path + optional query). Tranco only gives
# domain,rank -- no path -- so every benign training URL was previously a
# bare domain root (`https://{domain}`), which taught the classifier "any
# URL path at all -> phishing" as a near-deterministic rule (found via a
# live-extension false positive on an ordinary /about page; see
# PROJECT_BRIEF.md, Phase 9 "path_length artifact" entry). These templates
# give the benign class the path/query variety real browsing actually has,
# without live-fetching arbitrary real subpages.
_BENIGN_PATH_TEMPLATES = [
    "",  # bare root -- still a real, common case, kept in the mix
    "/about",
    "/about-us",
    "/contact",
    "/products",
    "/pricing",
    "/blog",
    "/blog/2024-year-in-review",
    "/news",
    "/help",
    "/support",
    "/docs",
    "/docs/getting-started",
    "/login",
    "/signup",
    "/search?q=example",
    "/user/profile",
    "/article/12345",
    "/category/electronics",
    "/wiki/Example_Article",
    "/en/products?page=2",
]

# Realistic benign subdomain prefixes. Same root cause as the path issue
# above, a second dimension of it: Tranco lists only the apex domain, so
# ~95% of benign training URLs had zero subdomains, vs. 12-27% for real
# phishing sources -- taught the classifier "any subdomain -> phishing"
# just as deterministically (found via a live false positive on
# en.wikipedia.org, num_subdomains=1). `None` = no prefix (bare apex is
# still common and legitimate), kept in the mix alongside real patterns.
_BENIGN_SUBDOMAIN_PREFIXES = [
    None, None, None,  # weighted toward bare apex -- still the common case
    "www",
    "en",
    "blog",
    "shop",
    "docs",
    "mail",
    "support",
    "app",
    "accounts",
    "news",
    "m",
]


def load_phishtank(csv_path: str | Path) -> list[Sample]:
    """Load PhishTank's `verified_online.csv` export.

    Expected columns include `url` (others are ignored). Rows with an
    empty URL are skipped rather than raising, since malformed rows are
    common in bulk exports.
    """
    path = Path(csv_path)
    samples: list[Sample] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("url") or "").strip()
            if not url:
                continue
            samples.append(Sample(url=url, label=1, source=Source.PHISHTANK))
    return samples


def load_openphish(feed_path: str | Path) -> list[Sample]:
    """Load OpenPhish's plaintext feed (one URL per line)."""
    path = Path(feed_path)
    samples: list[Sample] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            samples.append(Sample(url=url, label=1, source=Source.OPENPHISH))
    return samples


def load_tranco(csv_path: str | Path, limit: int | None = None, seed: int = 42) -> list[Sample]:
    """Load a Tranco top-sites list (`rank,domain` CSV, no header) as benign samples.

    Assigns each domain a deterministically-chosen realistic subdomain
    prefix (`_BENIGN_SUBDOMAIN_PREFIXES`, bare apex included) and subpage
    shape (`_BENIGN_PATH_TEMPLATES`, bare root included) rather than
    always the bare apex domain -- see those lists' comments for why: an
    all-bare-apex, all-bare-root benign class taught the classifier that
    any URL path or subdomain implies phishing. Deterministic via `seed`
    so loading the same file twice is reproducible.
    """
    path = Path(csv_path)
    rng = random.Random(seed)
    samples: list[Sample] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break
            if len(row) < 2:
                continue
            domain = row[1].strip()
            if not domain:
                continue
            prefix = rng.choice(_BENIGN_SUBDOMAIN_PREFIXES)
            host = f"{prefix}.{domain}" if prefix else domain
            suffix = rng.choice(_BENIGN_PATH_TEMPLATES)
            samples.append(Sample(url=f"https://{host}{suffix}", label=0, source=Source.TRANCO))
    return samples


def load_llm_generated(jsonl_path: str | Path) -> list[Sample]:
    """Load the local LLM-generated phishing partition written by
    `phishshield.data.generation.save_samples_jsonl`.

    Only reads from `data/generated/` snapshots already produced by
    `generate_llm_phishing_dataset` — this loader makes no LLM calls itself.
    """
    path = Path(jsonl_path)
    samples: list[Sample] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            samples.append(
                Sample(
                    url=record["url"],
                    label=record["label"],
                    source=Source(record["source"]),
                    html=record.get("html"),
                    brand_target=record.get("brand_target"),
                )
            )
    return samples
