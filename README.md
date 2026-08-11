# [PROJECT_NAME]

## AI-Assisted Phishing Detection for Web Pages

## Academic Context

This is an academic research prototype developed as part of an
Information Security and Privacy (ISP) course project. It is **not an
official institute product or service** and should not be interpreted
as an institutional endorsement.

## Author

Naman Khatak
Indian Institute of Technology Mandi (IIT Mandi)
B.Tech — Data Science and Engineering
ISP Course Project

## Overview

This project investigates whether machine-learning models can identify
phishing-related **structural** characteristics of web pages (URL
shape, HTML/DOM structure), and whether **browser-rendered** training
data — capturing a page after real JavaScript execution, rather than a
static HTTP fetch — improves robustness on modern, JavaScript-heavy
websites. The full experimental account, including three major
data-construction bugs found and fixed via live testing, is in
[`reports/FINAL_REPORT.md`](reports/FINAL_REPORT.md); this README is a
practical entry point, not a substitute for it.

## Research Question

Can a machine-learning system trained on structural characteristics of
web pages provide useful phishing-risk detection, and can
browser-rendered training data improve its robustness on modern
JavaScript-heavy websites?

## Architecture

```
Chrome Extension (page_extractor.js)
        |
        v
Page feature extraction (URL-lexical + HTML-structural, client-side)
        |
        v
FastAPI backend (phishshield.api.app)
        |
        v
V4 trained classifier (HistGradientBoostingClassifier)
        |
        v
Judge / risk fusion (alpha = 0.7)
        |
        v
Risk score (0-100) + LOW/SUSPICIOUS/HIGH band + explanations
        |
        v
Popup UI / in-page warning overlay
```

- **Extension** (`extension/`): a Manifest V3 popup that analyzes the
  current tab only on explicit user click (`activeTab` + `scripting`
  permissions — no `<all_urls>`, no background scanning). Never reads
  form values, passwords, or cookies.
- **API** (`src/phishshield/api/`): FastAPI service exposing
  `/health`, `/demo-samples`, and `/analyze`.
- **Model**: the trained classifier artifact
  (`artifacts/phishing_classifier.joblib`), fused with a rule-based
  explainability judge.
- **UI**: the popup and the HIGH-risk in-page warning overlay
  (`page_overlay.js`).

## Features

Extracted identically on both the client (`page_extractor.js`) and
server (`phishshield.features`) sides — verified via automated
JS/Python parity tests:

- **URL-lexical**: length, dot/hyphen/digit counts and ratios, special
  characters, `@` symbol, IP-literal host, HTTPS, path/query length,
  suspicious TLD, port, subdomain count.
- **HTML-structural**: form count, password field count, text/email
  input count, iframe count, external JS script domains, external form
  actions, title/brand mismatch, hidden elements (`display:none`/
  `visibility:hidden`), favicon mismatch.

No feature reads page text semantically or uses NLP — this is a
structural, not a content-understanding, system. See
`reports/FINAL_REPORT.md` §3.1/§3.2 for what this does and does not
support claiming.

## Dataset

- **Legacy phishing**: PhishTank (verified feed), OpenPhish (free
  Community Feed).
- **Legacy benign**: Tranco top-domain list, with real fetched HTML for
  a subset.
- **LLM-generated phishing**: 144 real, live-generated samples (Gemini,
  6 brands x 6 tones), used as a held-out generalization test and
  partially folded into training.
- **Browser-rendered benign (v4)**: real Chromium (Playwright)
  captures — full JS execution, DOM settled — replacing static fetch
  as the canonical benign-data capture method after static fetch was
  found to systematically undercount `num_iframes`/
  `num_hidden_elements`/`num_external_js_domains` relative to what a
  real browser tab sends.
- **Hard-negative evaluation set**: 130 real, major websites (banks,
  universities, SaaS logins, docs, news) — kept separate from training
  wherever possible; §3.13 documents and corrects a case where this
  discipline slipped (81% domain overlap between an early v4 training
  batch and this set) before any release decision was made on it.
- **Domain-disjoint generalization set**: 28 pages from 32 domains
  verified programmatically to share zero domains with training data
  or the hard-negative set — the cleanest evidence in this project.

**Documented limitations**: OpenPhish's free feed only (not the full
academic feed); Tranco HTML fetch success rate ~77% (bot-blocking,
timeouts — logged, not silently dropped); single LLM provider (Gemini);
some benign captures required filtering out bot-block/CAPTCHA
interstitial pages that were initially miscaptured as real page
content (§3.13); static-vs-browser-rendered comparison on the phishing
side is based on a modest sample (up to 25 pages), not exhaustive.

## Model

- **Type**: `HistGradientBoostingClassifier` (scikit-learn), fused with
  a rule-based explainability judge: `risk = 0.7 * classifier_score +
  0.3 * judge_score` (`FUSION_ALPHA = 0.7`, unchanged since validation
  — see `reports/FINAL_REPORT.md` §5.3).
- **Current release artifact**: `artifacts/phishing_classifier.joblib`
  — v4, sha256 prefix `b6ed9eef36cd`. Frozen copies:
  `phishing_classifier_v3_current_frozen_70e68ee0.joblib` (rollback),
  `phishing_classifier_v4_frozen_b6ed9eef36cd.joblib`.
- **Feature count**: 27 (see Features above).
- **Risk bands**: LOW (score < 40), SUSPICIOUS/MEDIUM (40-69), HIGH
  (>= 70) — see `judge/judge.py:risk_band`.
- **Model loading**: loaded once per process (`lru_cache`); fails
  loudly (`FileNotFoundError`, no silent fallback) if the artifact is
  missing.

## Evaluation

Full detail in `reports/FINAL_REPORT.md` §3.13-3.14. Headline v3-vs-v4
comparison on the cleanest, domain-disjoint evidence:

| Dataset | v3 | v4 |
|---|---:|---:|
| Domain-disjoint browser-rendered benign, 28 pages | FPR 3.6%, 0 HIGH | **FPR 0%, 0 HIGH**, max score 35 |
| LLM-generated phishing holdout, 144 | recall 100% | recall 100% (unchanged) |
| Legacy phishing, sampled n=6300 | recall 97.52% | recall 97.58% (flat) |

These numbers describe performance on the specific evaluation
populations above — they are not a claim of universal, real-world
accuracy across the whole web. See Limitations.

## Calibration

Brier score: **0.0845** (n=8300, sampled real population; 0 = perfect,
0.25 = uninformative). Expected Calibration Error: **0.118** — the
model is measurably overconfident in the 0.3-0.9 predicted-score range
(a page scored 0.6 is empirically phishing about 14% of the time, not
60%). This is stated as a real limitation, not corrected — thresholds
were not changed in response. The LOW/SUSPICIOUS/HIGH bands users
actually see were tuned empirically against real hard-negative pages,
not derived from calibration, and are less affected by this finding
than raw `classifier_score` would be.

## Live Chrome Validation

Performed against v4, through the real unpacked extension, local
backend (`127.0.0.1:8000`) — see `reports/FINAL_REPORT.md` §3.14 for
the full table. Representative results:

| Site | Score | Band |
|---|---:|---|
| Google / YouTube / Wikipedia / GitHub | 3-13/100 | LOW |
| A bank careers page, two university/institutional logins | 8-19/100 | LOW |
| ChatGPT / Claude.ai | 11/100 | LOW |
| Overleaf editor | 33/100 | LOW (was 74/HIGH under v3) |
| Three personal Vercel-hosted apps | 66-69/100 | SUSPICIOUS (not HIGH) |
| Local phishing fixture | 100/100 | HIGH |
| LLM-generated phishing fixture | 100/100 | HIGH |

Both phishing fixtures triggered the HIGH-risk warning overlay with
correct reasons, and "Leave website"/"Continue anyway" both worked.
Zero legitimate pages tested scored HIGH.

**Not yet done**: live-Chrome testing against a deployed, non-localhost
backend (Render/Cloud Run) — see `DEPLOYMENT.md`.

## UI/UX

The popup implements distinct, non-overlapping states: idle, analyzing
(spinner), result (LOW/SUSPICIOUS/HIGH card with expandable "View
Details"), and explicit, named error states (offline, model
unavailable, rate-limited, malformed response) with a Retry button — a
CSS cascade bug that let two of these states render simultaneously was
found via live testing and fixed, with a regression test asserting
actual computed visibility, not just class presence (see
`reports/FINAL_REPORT.md` §3.10).

A HIGH verdict additionally injects an in-page warning overlay
(`page_overlay.js`, closed Shadow DOM) with "Leave website"/"Continue
anyway" and keyboard accessibility (focus trap, Escape to dismiss,
ARIA roles). This has not been certified against a formal accessibility
standard (e.g. WCAG) — only manually verified.

## Limitations

- Structural, not semantic: the model has no channel onto page *text*
  meaning, so it cannot detect phishing solely from persuasive copy.
- The offline `legacy_test` aggregate (dominated by URL-only,
  no-fetched-HTML samples) has never dropped below ~22-30% FPR across
  any fix in this project — a research-methodology artifact of the
  no-live-scraping constraint, not something the live extension itself
  experiences (a real browser tab always has a DOM).
- Calibration is measurably imperfect (see above).
- No live-WHOIS/SSL/DNS lookups, no domain reputation/age signal — out
  of scope by design (see `PROJECT_BRIEF.md`).
- Docker image has been reviewed but not built/run in every
  environment this project has been developed in — verify locally
  before relying on it.
- This is a research prototype: **do not present it as guaranteed
  phishing protection, commercial-grade antivirus, or a system with
  zero false positives.**

## Privacy

See [`PRIVACY_POLICY.md`](PRIVACY_POLICY.md) for the full policy. In
short: the extension only analyzes the current tab on explicit user
click, sends a numeric structural feature vector (never raw HTML, form
values, or passwords) to the configured backend, and the backend does
not log request bodies or feature payloads (see `SECURITY_REVIEW.md`
and `src/phishshield/api/app.py`'s logging middleware).

## Local Setup

See [`LOCAL_SETUP.md`](LOCAL_SETUP.md) for full instructions. Quick
start:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn phishshield.api.app:app --port 8000
```

Then load `extension/` as an unpacked extension in
`chrome://extensions` (Developer mode -> Load unpacked).

## Deployment

Not yet publicly deployed. See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the
prepared (but not executed) production deployment plan, and
`reports/FINAL_REPORT.md` §8.1 for the current release gate status.

## Project Structure

```
src/phishshield/
  api/        FastAPI app, model loading, schemas
  data/       dataset schema, loaders, LLM generation, splits, pipeline
  features/   URL and HTML feature extractors
  judge/      rule-based explainability judge
  models/     classifier training, evaluation, export, report assets
extension/    Manifest V3 popup + in-page warning overlay
scripts/      data-capture, evaluation, and packaging scripts
tests/        Python unit/integration tests
tests_js/     JS/Python feature-parity and popup/overlay behavior tests
reports/      FINAL_REPORT.md and generated report assets
data/         raw/generated datasets and evaluation manifests (mostly gitignored)
artifacts/    trained model artifacts
```

## Academic Disclaimer

[PROJECT_NAME] is an academic research prototype developed by Naman
Khatak as part of an ISP course project at the Indian Institute of
Technology Mandi. It is not an official IIT Mandi product or service
and should not be interpreted as an endorsement by IIT Mandi.

## License

Not yet specified.
