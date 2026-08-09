"""Loaders that normalize raw dataset snapshots into `Sample` objects.

All loaders read local files only (no live network calls) — snapshots are
expected to already be downloaded into `data/raw/` (see the project brief,
Phase 1 acceptance criteria). Fetching those snapshots is a separate concern
from this module.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from phishshield.data.schema import Sample, Source


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


def load_tranco(csv_path: str | Path, limit: int | None = None) -> list[Sample]:
    """Load a Tranco top-sites list (`rank,domain` CSV, no header) as benign samples."""
    path = Path(csv_path)
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
            samples.append(Sample(url=f"https://{domain}", label=0, source=Source.TRANCO))
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
