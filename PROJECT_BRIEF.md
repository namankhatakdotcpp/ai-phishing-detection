# PhishShield AI — Project Brief

## 1. What we're building

A research project (not a production tool) for an Information Security and
Privacy course, submitted as a semester deliverable. The core contribution:

> Standard phishing-detection classifiers are trained on legacy, human-authored
> phishing datasets (PhishTank, OpenPhish). LLMs can now generate fresh,
> well-written phishing content in seconds. We measure the resulting
> **detection gap** between legacy and LLM-generated phishing, then show a
> mitigation (adding LLM-generated examples to training, plus an LLM-judge
> reasoning layer as a second signal).

Secondary deliverable: a thin browser-extension demo that calls the trained
model on a curated set of examples (not a live real-time production pipeline —
say so explicitly in the report).

## 2. Hard constraints (do not violate)

- **No live scraping of active malicious/phishing sites.** Use only static,
  already-collected datasets (PhishTank CSV/API, OpenPhish feed, Tranco
  top-1M for benign URLs).
- **LLM-generated phishing content is a local research artifact only.** It is
  never hosted, never sent to real users, never used outside this dataset.
  State this explicitly in code comments and the final report.
- **No live WHOIS/SSL/DNS lookups in the demo path.** Precompute or mock
  these features from dataset snapshots — this is a research prototype, not
  a production security product.
- **No AI attribution anywhere** — not in commits, README, code comments, or
  the report. Conventional Commits style (`feat:`, `fix:`, `refactor:`,
  `docs:`, `test:`, `perf:`, `chore:`), small atomic commits, one logical
  change per commit.
- Production-quality code: clean architecture, SOLID where it actually
  applies (don't over-abstract a course project), meaningful names, proper
  error handling, no dead code, tests for the core pipeline logic.
- LLM calls (dataset generation, judge module) are **mocked/stubbed** for
  this deadline, noted as future work in the report — not real API calls.

## 3. Tech stack

- **Data/ML**: Python, pandas, scikit-learn `HistGradientBoostingClassifier`
  (baseline classifier — swapped in for XGBoost to avoid a `libomp` native
  dependency that isn't available in every dev environment),
  BeautifulSoup (HTML feature extraction), matplotlib/seaborn (eval plots).
- **LLM-judge module**: mocked for the deadline — structured stub responses
  matching the shape a real LLM call would return, swappable later.
- **Backend for the demo**: FastAPI, single `/analyze` endpoint that takes a
  precomputed feature set (or a page from the curated demo set) and returns a
  risk score + explanation.
- **Extension**: Manifest V3, vanilla JS, calls the FastAPI backend against
  the curated demo set only — not a real-time crawler.

## 4. Repo structure

```
phishshield/
  data/
    raw/                  # downloaded PhishTank/OpenPhish/Tranco snapshots (gitignored)
    generated/             # LLM-generated phishing set (gitignored, local-only)
    processed/             # feature-extracted, split datasets
  src/
    phishshield/
      features/            # HTML + URL feature extraction
      data/                # dataset loading, splitting, generation scripts
      models/               # classifier training/inference
      judge/                # LLM-judge module
      api/                  # FastAPI app
  tests/
  extension/                # Manifest V3 demo extension
  notebooks/                 # exploratory analysis only, not pipeline logic
  reports/                    # eval plots, tables, final writeup assets
```

## 5. Build phases

### Phase 1 — Feature extraction + data loading (done)
- Unified sample schema; PhishTank/OpenPhish/Tranco loaders.
- HTML structural features (forms, external JS domains, iframes,
  title/brand mismatch) and URL lexical features (length, subdomain count,
  IP-literal host, special-char ratio).
- Unit tests on hand-crafted fixtures; leakage check (label never reaches
  feature extraction).

### Phase 2 — LLM-generated phishing dataset (mocked)
- Script that generates N phishing HTML/email samples via a stubbed
  generation function across a fixed brand list and obfuscation/tone
  variants, saved locally under `data/generated/` (gitignored).
- Held out entirely from the initial training split.

### Phase 3 — Baseline classifier + evaluation harness
- Train on legacy data only; report precision/recall/F1/FPR separately on
  legacy held-out set vs. LLM-generated set. Headline plot: performance
  drop legacy → LLM-generated.

### Phase 5 — minimal LLM-judge module (mocked) + reproducibility logging
- Given structured features (not raw HTML), produce a structured risk
  explanation (score + bullet reasons) via a deterministic rule engine
  standing in for a real LLM call, matching the "Risk Score: 91% —
  reasons..." format. Swappable for a real API later — built ahead of
  schedule because Phase 4's fusion ablation needs a judge score to fuse.
- Every "prompt" (feature dict)/"response" (verdict) pair the judge
  produces during an evaluation run is logged as JSONL
  (`save_judge_log`), wired into `run_mitigation_experiment` via
  `judge_log_path` and tagged by partition, for reproducibility.

### Phase 4 — Mitigation experiment
- Re-train with a portion of LLM-generated data folded into training;
  evaluate before/after on the same held-out sets (legacy_test untouched,
  LLM-generated remainder after folding).
- Ablation: classifier-only vs. classifier+judge score fusion, evaluated on
  the mitigated ("after") model.

### Phase 6 — Demo API + extension
- FastAPI `/analyze` + `/demo-samples` endpoints, backed by a
  self-contained demo classifier (trained from in-repo synthetic patterns
  + the mocked LLM-generated set — not the real Phase 3/4 result) fused
  with the Phase 5 judge, matching the pitch's "Risk Score: N% —
  reasons..." format.
- Manifest V3 popup extension over the curated demo set only — no
  `activeTab`/`scripting` permission, `host_permissions` scoped to
  `localhost:8000`, never reads the page the user is on.

### Phase 7 — Report assets
- `build_report_assets` generates dataset stats, the Phase 3 eval table,
  the Phase 4 before/after + ablation tables, and two qualitative examples
  (one legacy phishing correctly caught, one LLM-generated sample the
  baseline misses but the mitigated model catches) into `reports/`.
- Defaults to `phishshield.data.synthetic`'s self-contained legacy pool so
  it runs with no downloaded data — clearly labeled as illustrative, not
  the report's real headline numbers. Accepts
  `--phishtank`/`--openphish`/`--tranco` to run on real data instead.

### Phase 8 — Real LLM wiring for dataset generation
- `phishshield.data.llm_client.AnthropicLureClient` makes real Anthropic API
  calls (default `claude-opus-5`, `effort="low"` — a short, non-reasoning-
  heavy generation task) to write the persuasive lure copy (title + one
  paragraph) for each (brand, tone) pair. The page skeleton (password
  field, external form action/script, hidden element) stays deterministic
  either way, so mock and live samples exercise the Phase 1 feature
  extractors identically.
- `generate_llm_phishing_dataset(seed, llm_client=None, max_samples=None)`
  keeps its interface stable: mock (default, `llm_client=None`, free) vs.
  live (pass any client implementing `generate_lure(brand, tone) ->
  LureCopy`) only changes where the lure copy comes from. `TONES` was
  expanded from 2 to 6 categories (`urgent`, `formal`, `reward`,
  `security_alert`, `invoice`, `delivery`) — otherwise obfuscation alone
  varies the domain, not the lure content, so padding via `max_samples`
  would repeat identical copy across samples and weaken the
  legacy-vs-LLM robustness claim. Grid is now 6 brands × 6 tones × 4
  obfuscations = **144 samples**, from **36 unique (brand, tone) lure
  calls** (cached and reused across the 4 obfuscation techniques per
  pair, same caching behavior as before).
- Every live call and its raw response is appended to
  `data/generated/generation_manifest.jsonl` (gitignored) for methodology
  reproducibility — enough to check post hoc whether accuracy dropped on
  a specific tone category, without adding a field to the tested `Sample`
  schema.
- Retries: each `generate_lure()` call retries up to 3 times with
  exponential backoff (2s/4s/8s) on any exception (API error or
  malformed response), then raises `LureGenerationError` rather than
  degrading silently — a pair that fails after retries aborts the run
  instead of producing a sample mislabeled as live-generated.
- Two providers behind one interface (`phishshield.data.llm_client`):
  `GeminiLureClient` (default — `gemini-2.5-flash`, free tier via
  `GEMINI_API_KEY`/`GOOGLE_API_KEY`, `pip install -e ".[gemini]"`) and
  `AnthropicLureClient` (`claude-opus-5`, `ANTHROPIC_API_KEY`, `pip
  install -e ".[llm]"`). `build_lure_client(provider, model, effort)`
  dispatches between them; the CLI's `--provider` flag selects (default
  `gemini`). `--model` overrides the default per-provider model string if
  a newer one becomes the recommended free-tier default later.
- **Disclosure**: the default provider (Gemini) is used at the free tier,
  and Google may use free-tier traffic to improve their products (unlike
  the paid tier). The prompts/responses sent are short synthetic
  lure-copy requests for this research dataset only — no real user data,
  no PII — but this is worth stating plainly in the course report's
  methodology section rather than leaving it undisclosed.
- CLI (`generate_llm_dataset.py`): `--live` opts into real calls (default
  off); `--dry-run` prints the sample count, API call count, and a labeled
  cost ESTIMATE with **no network calls and no credentials required**
  (Gemini estimate is paid-tier rates with a note that free-tier usage is
  likely $0, subject to rate limits); `--max-samples` hard-caps both the
  dataset size and the live call count.
- Live smoke tests (`tests/live/test_real_generation_{anthropic,gemini}.py`)
  are skipped by default (no matching API key env var set) so the normal
  test suite never spends money or touches the network; run explicitly
  with a key set.
- **Credential handling**: keys are never passed as CLI arguments or typed
  into a chat/agent session — both leak into transcripts, shell history,
  or `ps aux`. `.env.example` documents the two supported env vars; the
  user copies it to gitignored `.env` and fills it in directly (not by
  asking an agent to write the value into a command). `llm_client.py`
  loads `.env` via `python-dotenv`; `describe_env_key(provider)` confirms
  presence with a masked prefix/suffix only, and the CLI prints that
  check (never the key) before every `--live` run. A tracked
  `.githooks/pre-commit` hook (`git config core.hooksPath .githooks`)
  blocks any commit where `.env.example` carries a non-empty secret value
  or another staged file matches a KEY=/TOKEN=/SECRET= pattern — added
  after a real incident where a key was typed into `.env.example` instead
  of `.env`; the hook is the backstop for that exact mistake, checked
  before commit rather than caught after the fact.
- **Canary run complete** (2026-08-10): ran live against Gemini with a
  rotated key. Two bugs found and fixed before trusting the output:
  1. `GEMINI_DEFAULT_MODEL` was `gemini-2.5-flash`, which now 404s for
     new-user keys ("no longer available to new users") — switched to
     `gemini-flash-latest`, an alias Google maintains to track the
     current model, so this doesn't go stale the same way again.
  2. `response_schema` included `additionalProperties`, which Gemini's
     restricted OpenAPI schema subset rejects outright (400
     INVALID_ARGUMENT) — Anthropic's full JSON Schema support doesn't
     have this restriction, so the two providers now use separate
     schema constants (`_LURE_SCHEMA` vs. `_GEMINI_LURE_SCHEMA`).
  3. A real, load-bearing finding: the `urgent` tone was refused by
     Gemini's safety classifier on one attempt ("I cannot fulfill this
     request...") — but it came back as schema-valid JSON
     (`{"title": "Refusal", "lure_copy": "I cannot fulfill..."}"`),
     which parsed cleanly and would have been silently saved as a
     normal, mislabeled sample. Refusal was non-deterministic — a retry
     on the same tone succeeded cleanly. Added `_looks_like_refusal()`
     as a guard in both clients' response handling (checked before the
     retry-eligible return, so a caught refusal now retries like any
     other failure instead of silently corrupting the dataset).
  - Quality check on the resulting output (urgent vs. formal, same
    brand): genuinely distinct framing — urgent used a 24-hour
    suspension threat, formal used routine-review language — not
    synonym-swapped from a shared template. Exfil host was our own
    synthetic placeholder (`beacon.credential-sink.top`), no real
    brand wording copied verbatim. Passed both the variety check and
    the non-liftability check before proceeding.
- **Full 144-sample live run complete** (2026-08-10), output at
  `data/generated/llm_phishing_v1.jsonl` (gitignored). Two more issues
  found and fixed en route:
  1. `gemini-flash-latest` resolved to `gemini-3.6-flash` under the
     hood, whose free tier caps at **20 requests/day/project/model** —
     testing during the canary phase alone used most of that. Switched
     to `gemini-flash-lite-latest` for the full run (separate quota
     bucket, untouched), re-canaried at 8 samples before trusting it.
  2. `gemini-flash-lite-latest` hit a **15 requests/minute** free-tier
     cap — our fixed exponential backoff (2s/4s/8s ≈ 14s total) wasn't
     reliably long enough to clear a per-minute window. Fixed two ways:
     `_suggested_retry_delay()` now parses the API's own `retryDelay`
     out of a 429 response and waits that long (+1s margin) instead of
     the fixed backoff; `GeminiLureClient` also self-paces at a 4.5s
     minimum interval between calls so it avoids the ceiling proactively
     rather than only reacting after hitting it.
  - Result: clean run, zero retries needed, 144 samples / 36 unique
    lure texts, evenly distributed (24 samples per brand). Re-scanned
    the full output with `_looks_like_refusal()` after the fact — zero
    refusal artifacts made it into the dataset. Spot-checked Microsoft
    and Chase across all 6 tones — genuinely distinct framing per tone
    (urgent/formal/reward/security_alert/invoice/delivery), not
    templated. Round-trips cleanly through the existing Phase 1 feature
    pipeline with no loader/extractor changes needed.
- **Phase 3/4/7 re-run against the real LLM-generated partition**
  (2026-08-10): `build_report_assets --llm-generated
  data/generated/llm_phishing_v1.jsonl` — legacy side is still the
  synthetic pool (Phase 9's real PhishTank/OpenPhish/Tranco download
  hasn't happened yet), but the LLM-generated side is now the real
  144-sample dataset, not the mocked grid. `run()`'s mode label was
  fixed to state legacy/llm_generated provenance separately
  (`legacy: synthetic (illustrative only); llm_generated: real (loaded
  from ...)`) rather than one combined string that went stale the
  moment only one side became real.
  - **Headline result**: baseline (legacy-only) classifier recall on
    the real LLM-generated holdout is **97.2%** (140/144) — already
    high, because the structural signals it learned from
    hand-templated/synthetic legacy phishing (password field, external
    form action, off-domain script) generalize to genuinely
    LLM-authored lure copy; the gap this project set out to measure is
    real but smaller than the illustrative synthetic run suggested.
    Folding half the real LLM data into training closes it to **100%**
    on the untouched remainder. Classifier+judge fusion made no
    further difference in this run (both already at 100% recall on
    the after-mitigation model) — an honest null result worth stating
    as-is rather than reaching for a fusion benefit that isn't there
    yet at this sample size.
  - Qualitative flip example is now a real generated sample:
    `https://chaase.com/account/verify-now` (Chase, homoglyph
    obfuscation) — missed by the before-model (score 0.0), caught
    after mitigation (score 1.0).
  - **Caveat for the report**: this is not yet the final result — the
    legacy side needs Phase 9's real downloaded data before the
    reported gap is fully trustworthy. A synthetic legacy classifier
    may over- or under-generalize to real LLM phishing in ways a
    classifier trained on real PhishTank/OpenPhish data would not.
  - **Next**: Phase 9 (real PhishTank/OpenPhish/Tranco ingestion), then
    a final Phase 3/4/7 re-run with both sides real.

## 6. What "done" looks like

A reproducible pipeline, a working local demo, and a `reports/` folder with
evidence for the core claim — not a deployed product, not a real-time
crawler. Honesty about limitations in the final report is worth more marks
than overclaiming.
