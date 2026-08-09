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

**Phase 2 complete**: mocked LLM-generated phishing dataset (templated, no
real API calls — see `phishshield.data.generation` for the ethical/scope
constraint), persisted to gitignored `data/generated/`, plus a
train/legacy-test/LLM-holdout split helper that keeps the LLM-generated
partition out of training until Phase 4 explicitly folds a fraction in.

```
src/phishshield/
  data/       schema, loaders, generation (mocked LLM), splits, pipeline
  features/   URL and HTML feature extractors
tests/        unit tests + fixtures (tests/fixtures/)
```

**Phase 3 complete**: baseline gradient-boosted tree classifier
(`HistGradientBoostingClassifier` — swapped in for XGBoost, whose macOS
wheels need a `libomp` Homebrew install not available in every dev
environment) trained on legacy data only, plus an evaluation harness
reporting precision/recall/F1/FPR per partition and a headline
legacy-vs-LLM-generated comparison plot. LLM-generated samples are
phishing-only by construction, so FPR is reported as NaN (not an error) on
that partition — it has no true negatives to be structurally defined
against.

```
src/phishshield/
  data/       schema, loaders, generation (mocked LLM), splits, pipeline
  features/   URL and HTML feature extractors
  models/     classifier, evaluation harness, plotting, train_baseline CLI
tests/        unit tests + fixtures (tests/fixtures/)
```

Regenerate the LLM-phishing partition with:

```bash
python -m phishshield.data.generate_llm_dataset
```

Run the Phase 3 experiment (requires PhishTank/OpenPhish/Tranco snapshots
already downloaded into `data/raw/` — see PROJECT_BRIEF.md, Phase 1):

```bash
python -m phishshield.models.train_baseline \
    --phishtank data/raw/verified_online.csv \
    --openphish data/raw/openphish_feed.txt \
    --tranco data/raw/tranco_top1m.csv \
    --llm-generated data/generated/llm_phishing_v1.jsonl
```

Phases 4–7 (mitigation experiment, LLM-judge module, demo API + extension,
report assets) are not yet started.
