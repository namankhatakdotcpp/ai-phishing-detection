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

**Phase 5 complete**: a mocked, rule-based judge (`phishshield.judge.judge`)
turns extracted structured features into a "Risk Score: N% — reasons..."
verdict — deterministic, no real LLM calls, swappable for a real API later.
Built ahead of Phase 4 since the fusion ablation needs a judge score. Every
feature-dict/verdict pair the judge produces during an evaluation run can be
logged as JSONL (`judge_dataframe(df, log=...)` + `save_judge_log`), wired
into the mitigation experiment via `judge_log_path` and tagged by partition,
for reproducibility.

**Phase 4 complete**: mitigation experiment
(`phishshield.models.mitigation.run_mitigation_experiment`) trains a
"before" model on legacy data only and an "after" model with a fraction of
the LLM-generated partition folded in, evaluating both on the same
untouched held-out sets. Also ablates classifier-only vs.
classifier+judge-fusion (`phishshield.models.fusion.fuse_scores`) on the
mitigated model. Note: in this toy dev environment the mocked LLM-generated
templates share structural features (password field, external form action)
with the hand-crafted legacy fixtures, so the "before" model already
generalizes well to them — the Phase 3/4 headline gap is expected to be
much more pronounced once run against real downloaded PhishTank/OpenPhish
data and a less feature-similar generation approach.

```
src/phishshield/
  data/       schema, loaders, generation (mocked LLM), splits, pipeline
  features/   URL and HTML feature extractors
  judge/      mocked structured risk-explanation judge
  models/     classifier, evaluation harness, fusion, mitigation experiment,
              plotting, train_baseline / run_mitigation CLIs
tests/        unit tests + fixtures (tests/fixtures/)
```

Run the Phase 4 experiment (same local dataset requirements as Phase 3;
writes a judge evaluation log to `reports/phase4_judge_log.jsonl` by
default — pass `--judge-log ''` to skip):

```bash
python -m phishshield.models.run_mitigation \
    --phishtank data/raw/verified_online.csv \
    --openphish data/raw/openphish_feed.txt \
    --tranco data/raw/tranco_top1m.csv \
    --llm-generated data/generated/llm_phishing_v1.jsonl
```

Phases 6–7 (demo API + extension, report assets) are not yet started.
