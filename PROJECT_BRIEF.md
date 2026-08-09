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

- **Data/ML**: Python, pandas, scikit-learn + XGBoost (baseline classifier),
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

### Phase 4 — Mitigation experiment
- Re-train with a portion of LLM-generated data folded into training.
- Ablation: classifier-only vs. classifier+judge fusion.

### Phase 5 — LLM-judge module (mocked)
- Given structured features (not raw HTML), produce a structured risk
  explanation (score + bullet reasons) via a stubbed call, matching the
  "Risk Score: 91% — reasons..." format. Swappable for a real API later.

### Phase 6 — Demo API + extension
- FastAPI `/analyze` endpoint; Manifest V3 extension over the curated demo
  set only.

### Phase 7 — Report assets
- Dataset stats, eval tables, ablation table, qualitative examples.

## 6. What "done" looks like

A reproducible pipeline, a working local demo, and a `reports/` folder with
evidence for the core claim — not a deployed product, not a real-time
crawler. Honesty about limitations in the final report is worth more marks
than overclaiming.
