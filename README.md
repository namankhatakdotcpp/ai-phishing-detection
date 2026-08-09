# PhishShield AI — research pipeline

Research prototype for an Information Security and Privacy course project.
Measures the detection gap between phishing classifiers trained on legacy
datasets (PhishTank, OpenPhish) and freshly LLM-generated phishing content,
then evaluates a mitigation. See `PROJECT_BRIEF.md` for full scope, phases,
and hard constraints (no live scraping, no live WHOIS/SSL/DNS lookups, no
hosting of generated phishing content).

This is a research prototype, not a production security product.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest
```

## Status

**Phase 1 complete**: URL lexical feature extraction, HTML structural
feature extraction, dataset loaders (PhishTank/OpenPhish/Tranco), and a
leakage-free feature pipeline, with unit tests over hand-crafted fixtures.

```
src/phishshield/
  data/       schema, loaders, feature-dataframe pipeline
  features/   URL and HTML feature extractors
tests/        unit tests + fixtures (tests/fixtures/)
```

Phases 2–7 (LLM-generated dataset, baseline classifier, mitigation
experiment, LLM-judge module, demo API + extension, report assets) are not
yet started.
