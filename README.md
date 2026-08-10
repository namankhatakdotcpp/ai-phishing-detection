# PhishShield AI — research pipeline

Research prototype for an Information Security and Privacy course project.
Measures the detection gap between phishing classifiers trained on legacy
datasets (PhishTank, OpenPhish) and freshly LLM-generated phishing content,
then evaluates a mitigation. See `PROJECT_BRIEF.md` for full scope, phases,
and hard constraints (no live scraping, no live WHOIS/SSL/DNS lookups, no
hosting of generated phishing content).

This is a research prototype, not a production security product. A v1
extension UX and production-deployment prep exist (see `LOCAL_SETUP.md`,
`SECURITY_REVIEW.md`, `PRIVACY_POLICY.md`, `DEPLOYMENT.md`), but nothing
is deployed publicly and no Chrome Web Store submission has happened.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks   # blocks committing a real secret into a tracked file
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

**Phase 6/9 complete**: FastAPI demo backend (`phishshield.api.app`) with
`GET /health`, `GET /demo-samples`, and `POST /analyze`, backed by the
**real Phase 9 classifier** (`artifacts/phishing_classifier.joblib`,
loaded once at startup by `phishshield.api.model_store` — an earlier
self-contained synthetic-only demo model was replaced after live testing
found it gave backwards verdicts) fused with the Phase 5 judge at
`alpha=0.7`. `/analyze` accepts either a curated `sample_id` or a
caller-supplied precomputed `features` dict, plus optional display-only
`url`/`title`.

**Extension (v1 security-assistant UX)**: the Manifest V3 popup
(`extension/`) analyzes the **current tab** on click, not a curated demo
set. It uses `activeTab` + `scripting` — Chrome's narrower alternative to
standing host permissions: access is granted only after the user's
explicit click, only for that tab. `page_extractor.js` computes the same
URL-lexical / HTML-structural feature schema as the Python pipeline
client-side and sends only that numeric feature vector to `/analyze` —
never the page's raw HTML, never form/input values, so no typed
credentials are ever collected. The popup shows a LOW/SUSPICIOUS/HIGH
risk card with expandable reasons; a HIGH verdict also injects an
in-page warning overlay (`page_overlay.js`, closed Shadow DOM, all
dynamic text via `textContent` only — never `innerHTML`) with "Leave
website"/"Continue anyway". `host_permissions` stays scoped to
`localhost:8000`/`127.0.0.1:8000`; there is no `<all_urls>` grant and no
background/persistent scanning. See `extension/README.md` for the exact
contract and known limitations (real, measured FPR; local-only backend;
structural not semantic features).

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
tailor. Note this is prose text, not a feature the classifier's URL-lexical
/ HTML-structural feature space reads (see `reports/FINAL_REPORT.md`
§3.2/§6): live-generating it makes the *dataset* more realistic, it does
not by itself let this project's experiments measure robustness to
LLM-authored content specifically. The page skeleton (password field,
external form action, script) stays deterministic either way, so mock and live
output stay structurally comparable. `generate_llm_phishing_dataset()`
keeps its existing signature — pass `llm_client=None` (default, free,
deterministic) or a real client (cached per brand+tone pair — 36 calls
for the full 144-sample grid: 6 brands × 6 tones × 4 obfuscations).
`TONES` was expanded from 2 to 6 (`urgent`, `formal`, `reward`,
`security_alert`, `invoice`, `delivery`) so obfuscation isn't the only
thing varying between samples — otherwise most of a padded-up dataset
would share identical lure copy. Every live call is logged to
`data/generated/generation_manifest.jsonl` (gitignored) for methodology
reproducibility, and each call retries up to 3x with exponential backoff
before the run aborts on a persistently failing pair.

Two providers, one interface — `build_lure_client(provider, model,
effort)`:

| Provider | Client | Default model | Key | Install |
|---|---|---|---|---|
| `gemini` (default) | `GeminiLureClient` | `gemini-flash-latest` | `GEMINI_API_KEY` / `GOOGLE_API_KEY` (free tier) | `pip install -e ".[gemini]"` |
| `anthropic` | `AnthropicLureClient` | `claude-opus-5` | `ANTHROPIC_API_KEY` | `pip install -e ".[llm]"` |

The Gemini default is the `gemini-flash-latest` *alias*, not a dated
model string — `gemini-2.5-flash` (the original default) started 404ing
for new-user keys ("no longer available to new users") partway through
this project, which is exactly the kind of drift an alias avoids.

**Disclosure**: at the free tier, Google may use Gemini traffic to
improve their products (unlike the paid tier). What's sent is short
synthetic lure-copy requests for this research dataset only — no real
user data — but say so plainly in the report's methodology section.
`--model` overrides the default if needed.

**Refusal detection**: structured output (`response_schema`) guarantees
JSON *shape*, not that the model actually complied — a safety-filtered
`urgent`-tone request came back as valid JSON
(`{"title": "Refusal", "lure_copy": "I cannot fulfill this request..."}`)
that would otherwise have been saved as a normal, silently mislabeled
sample. `_looks_like_refusal()` catches this pattern in both clients and
routes it through the same retry path as any other failure — observed
refusal rate was non-deterministic (same prompt succeeded on retry).

**Credential handling — never paste a key into a chat/agent session or a
CLI argument.** Both land the raw secret in a transcript, shell history,
or `ps aux`. Copy `.env.example` to `.env` (gitignored) and fill in the
key yourself, in your own editor/terminal — `llm_client.py` loads it via
`python-dotenv` automatically. `describe_env_key(provider)` confirms
presence with only a masked prefix/suffix, never the full value, and the
CLI prints that check (not the key) before every `--live` run.

**Full 144-sample live run complete (2026-08-10)** — output at
`data/generated/llm_phishing_v1.jsonl` (gitignored), 36 unique lure
texts across 6 brands × 6 tones, 24 samples each. Checked before and
after: variety (spot-checked all 6 tones for two brands — genuinely
distinct framing, not synonym-swapped), non-liftability (synthetic
exfil host, no verbatim real-brand wording), and zero refusal artifacts
(re-scanned the full output with `_looks_like_refusal()` after the
fact). Round-trips cleanly through the existing Phase 1 feature
pipeline. Hit two free-tier quirks along the way, both fixed:
`gemini-flash-latest`'s underlying model has only a 20/day free quota
(exhausted by testing) — switched to `gemini-flash-lite-latest` for a
separate quota bucket; that model then hit a 15/minute cap, fixed by
parsing the API's actual `retryDelay` instead of a fixed backoff and
adding a 4.5s self-paced interval between calls.

**Phase 3/4/7 re-run against the real partition (2026-08-10)**:
`python -m phishshield.models.build_report_assets --llm-generated
data/generated/llm_phishing_v1.jsonl` — legacy side is still the
synthetic pool (Phase 9 isn't done), LLM-generated side is now real.
Headline: baseline recall on the real LLM holdout is **97.2%**
(140/144) — high, because structural signals generalize well, but a
real, nonzero gap; folding half the real data into training closes it
to **100%**. Judge fusion added nothing further in this run (both
already at 100% after mitigation) — reported as an honest null result.
**Caveat**: not the final number — the legacy side still needs Phase
9's real downloaded data before this gap is fully trustworthy. Next:
Phase 9, then a final re-run with both sides real.

**Phase 9: real legacy data + benign HTML + judge fusion tuning
(2026-08-10)**: downloaded real PhishTank (71,175 URLs), OpenPhish's
free feed (300 URLs), and 5,000 Tranco domains. An initial fully-real
run showed a suspicious 100% recall on the LLM holdout; ablation
confirmed it's genuinely driven by URL-lexical pattern transfer, not a
`has_html` shortcut, but also exposed that real legacy training data
never contains real HTML for either class (no live scraping of
phishing pages), making the HTML feature dimension untestable. Fixed
by adding `fetch_tranco_html.py` to fetch real front-page HTML for 157
top-ranked (legitimate, safe-to-fetch) Tranco domains — the model now
correctly classifies all 41 real-HTML benign test samples as benign
(0% FPR on that slice), resolving the concern rather than masking it.
Final real-data baseline: **99.5% recall / 2.6% FPR** on 15,295 real
`legacy_test` samples, **100% recall** on the 144-sample real LLM
holdout. Also found the default 50/50 judge fusion (`alpha=0.5`)
collapses `legacy_test` recall to **16.5%** — the mock judge scores 0
on ~84% of real phishing URLs since its rules target blatant markers
real-world phishing avoids — and fixed it by sweeping alpha and
changing the default to **`alpha=0.7`**: **99.94% precision / 99.50%
recall / 0.8% FPR**, cutting FPR by more than two-thirds vs.
classifier-only for a 0.05-point recall cost. Remaining gap: OpenPhish
free feed (not full academic access), 157/300 Tranco HTML fetches
succeeded (rest blocked/timed out) — stated as honest limitations.

**Correction**: the numbers immediately above were later found to be
substantially an artifact of two real `load_tranco()` bugs (a benign
URL path/subdomain gap, discovered via live-extension testing against
real websites) — see `reports/FINAL_REPORT.md` Sections 3.5-3.9 for the
full corrected account. After fixing, a real evaluation against 46 real
major websites found 13.0% FPR, not 0%; further fixes (real login pages
and long documentation/wiki paths, both underrepresented in benign
training data) and a rescale to 130 real pages (Sections 3.8-3.9)
brought that down to **0.8% FPR at n=130, zero pages in the HIGH band**
— meaningfully better than before, with no measured phishing-recall
cost, but **the project is still not deployment-ready**: live Chrome
validation (an actual unpacked extension in an actual Chrome profile)
has never been run in this environment, which is now the primary
blocker rather than model quality. This paragraph is kept as a
historical record rather than silently edited; treat
`reports/FINAL_REPORT.md` as the current source of truth.

```bash
pip install -e ".[gemini]"
cp .env.example .env   # then edit .env yourself to add GEMINI_API_KEY=...
python -m phishshield.data.generate_llm_dataset --dry-run
# provider: gemini  model: gemini-flash-latest  effort: None
# total samples: 144 (full grid: 144)
# unique lure-copy API calls (cached per brand+tone pair): 36
# cost estimate (paid-tier rates): ~$0.04 — likely $0 on the free tier

# canary first, read the output, then the full grid (--model gemini-flash-lite-latest
# if you hit gemini-flash-latest's 20/day quota):
python -m phishshield.data.generate_llm_dataset --live --max-samples 4
python -m phishshield.data.generate_llm_dataset --live --max-samples 144
```

Phases 9–15 (real dataset ingestion, four-way eval matrix, deploy, Chrome
Web Store launch assets, report/demo-video finalization) are not started.
