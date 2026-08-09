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

**Phase 6 complete**: FastAPI demo backend (`phishshield.api.app`) with
`GET /demo-samples` and `POST /analyze`, backed by a self-contained demo
classifier (`phishshield.api.model_store` — trained from in-repo synthetic
patterns + the mocked LLM-generated set, *not* the real Phase 3/4 result,
which needs downloaded data this demo doesn't ship with) fused with the
Phase 5 judge. `/analyze` accepts either a curated `sample_id` or a
caller-supplied precomputed `features` dict. A Manifest V3 popup extension
(`extension/`) calls it over the curated demo set only — no
`activeTab`/`scripting` permission, `host_permissions` scoped to
`localhost:8000`, and it never reads the page the user is on. Verified
end-to-end in a browser against the live backend (dropdown populated from
`/demo-samples`, "Analyze" renders "Risk Score: N% — reasons...").

```
src/phishshield/
  api/        FastAPI app, demo classifier, curated demo samples, schemas
  data/       schema, loaders, generation (mocked LLM), splits, pipeline
  features/   URL and HTML feature extractors
  judge/      mocked structured risk-explanation judge
  models/     classifier, evaluation harness, fusion, mitigation experiment,
              plotting, train_baseline / run_mitigation CLIs
extension/    Manifest V3 demo popup (see extension/README.md to run it)
tests/        unit tests + fixtures (tests/fixtures/)
```

Run the demo backend, then load `extension/` as an unpacked extension (see
`extension/README.md`):

```bash
uvicorn phishshield.api.app:app --port 8000
```

**Phase 7 complete**: `phishshield.models.build_report_assets` generates
every report asset into `reports/` — dataset stats, the Phase 3
legacy-vs-LLM eval table + plot, the Phase 4 before/after + ablation
tables + plots, a judge evaluation log, and a qualitative-examples
markdown (one legacy phishing sample correctly caught, one LLM-generated
sample the baseline model misses but the mitigated model catches). Runs
by default on `phishshield.data.synthetic`'s self-contained legacy pool
(more varied than the fixture-based pool Phase 4's own tests use — 6
brands, several exfil domains) with no downloaded data required, and
labels its output "illustrative" throughout so it's never mistaken for
the real result. Interestingly, this richer synthetic pool *does* show a
partial legacy→LLM gap the earlier Phase 4 note didn't (before-model
recall on the LLM holdout drops to 0.875, closed to 1.0 after folding in
LLM-generated training data) — a small preview of the effect real
downloaded data should show more strongly. Pass
`--phishtank`/`--openphish`/`--tranco` (all three together) to run on real
data instead.

```
src/phishshield/
  api/        FastAPI app, demo classifier, curated demo samples, schemas
  data/       schema, loaders, generation (mocked LLM), synthetic legacy
              pool, splits, pipeline, dataset stats
  features/   URL and HTML feature extractors
  judge/      mocked structured risk-explanation judge
  models/     classifier, evaluation harness, fusion, mitigation
              experiment, qualitative examples, plotting,
              train_baseline / run_mitigation / build_report_assets CLIs
extension/    Manifest V3 demo popup (see extension/README.md to run it)
tests/        unit tests + fixtures (tests/fixtures/)
```

Generate the report assets (illustrative, no downloaded data needed):

```bash
python -m phishshield.models.build_report_assets
```

**Phase 8 in progress**: `phishshield.data.llm_client` wires a real LLM
call in for the persuasive lure copy (title + paragraph) per (brand, tone)
pair — the part of the generated phishing page an attacker would actually
tailor, and the part the project's "robustness against LLM-generated
phishing" claim is about. The page skeleton (password field, external
form action, script) stays deterministic either way, so mock and live
output stay structurally comparable. `generate_llm_phishing_dataset()`
keeps its existing signature — pass `llm_client=None` (default, free,
deterministic) or a real client (cached per brand+tone pair — 12 calls
for the full 48-sample grid).

Two providers, one interface — `build_lure_client(provider, model,
effort)`:

| Provider | Client | Default model | Key | Install |
|---|---|---|---|---|
| `gemini` (default) | `GeminiLureClient` | `gemini-2.5-flash` | `GEMINI_API_KEY` / `GOOGLE_API_KEY` (free tier) | `pip install -e ".[gemini]"` |
| `anthropic` | `AnthropicLureClient` | `claude-opus-5` | `ANTHROPIC_API_KEY` | `pip install -e ".[llm]"` |

**Not yet run for real** — no credentials for either provider have been
available in this environment. `--dry-run` shows the cost estimate with
no network calls needed:

```bash
pip install -e ".[gemini]"
python -m phishshield.data.generate_llm_dataset --dry-run
# provider: gemini  model: gemini-2.5-flash  effort: None
# total samples: 48 (full grid: 48)
# unique lure-copy API calls (cached per brand+tone pair): 12
# cost estimate (paid-tier rates): ~$0.01 — likely $0 on the free tier

# once GEMINI_API_KEY is set — canary first, read the output, then the full grid:
python -m phishshield.data.generate_llm_dataset --live --max-samples 4
python -m phishshield.data.generate_llm_dataset --live --max-samples 48
```

Phases 9–15 (real dataset ingestion, four-way eval matrix, deploy, Chrome
Web Store launch assets, report/demo-video finalization) are not started.
