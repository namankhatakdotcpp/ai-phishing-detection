# Contributing

## About the Project

[PROJECT_NAME] is an IIT Mandi ISP (Information Security and Privacy)
course project by Naman Khatak: a machine-learning-based phishing/
malicious-webpage risk detector, shipped as a Chrome extension backed
by a FastAPI service. It's an academic research prototype, not a
commercial product — see `README.md` for the full architecture,
dataset, model, and evaluation writeup, and `reports/FINAL_REPORT.md`
for the complete experimental account.

## Before Contributing

- Read `README.md` first to understand the project's actual scope and
  claims — this project makes deliberately narrow, experimentally
  supported claims, not general phishing-protection guarantees.
- This is a security-adjacent research project. **Do not submit**:
  malicious payloads, credential-stealing code, real phishing
  campaigns, or real user data of any kind.
  - Do not commit secrets, API keys, credentials, cookies, private
    data, or raw sensitive datasets.
  - Do not add real phishing page content to the repository — this
    project uses synthetic/local fixtures (`tests/fixtures/`,
    LLM-generated samples) for phishing test cases, never live
    scraped phishing pages, by design (see `PROJECT_BRIEF.md`).
  - Use synthetic/local fixtures for security testing whenever
    possible, matching the project's existing convention.

## Development Setup

See `LOCAL_SETUP.md` for the full setup process (Python environment,
running the backend, loading the extension). This file won't duplicate
those steps — follow `LOCAL_SETUP.md` directly.

## Repository Structure

```
src/phishshield/   Python package: API, data pipeline, feature
                    extractors, judge, model training/evaluation
extension/          Manifest V3 Chrome extension (popup + overlay)
scripts/            Data-capture, evaluation, and packaging scripts
tests/              Python unit/integration tests
tests_js/           JS/Python feature-parity and popup/overlay tests
reports/            FINAL_REPORT.md and generated report assets
data/               Raw/generated datasets and evaluation manifests
                    (mostly gitignored — see .gitignore)
artifacts/          Trained model artifacts
```

## Making Changes

1. Create a branch for your change.
2. Make focused changes — small, reviewable diffs are much easier to
   evaluate for a project in this space than large ones.
3. Add or update tests when you change behavior.
4. Run the existing test suite (see Testing Requirements below).
5. Check whether any documentation (`README.md`,
   `reports/FINAL_REPORT.md`, etc.) needs updating to stay accurate —
   this project treats stale documentation as a real defect, not a
   formality.
6. Review your own `git diff` before opening a pull request.
7. Submit a pull request using the template in
   `.github/PULL_REQUEST_TEMPLATE.md`.

## Testing Requirements

As of this writing, the project's full test suite (`pytest -q
--ignore=tests/live`, which includes the JS/Python parity tests) passes
156/156. Run it before submitting any change:

```bash
pytest -q --ignore=tests/live
```

This number will change legitimately as the project grows — the
requirement is "the suite passes and reflects your change," not that
the count stays exactly 156.

## Pull Requests

A good pull request:

- Has a clear, specific title.
- Explains **what** changed and **why** — the motivation matters as
  much as the diff in a research project like this one.
- States what testing was performed.
- Names any known limitations of the change.
- Includes screenshots for extension/UI changes, where useful.
- Never includes secrets or private data.

## Security-Sensitive Changes

Changes to the classifier, feature extraction, the judge/fusion logic,
or the API's security posture (CORS, rate limiting, request size
limits) require more explanation and testing than a typical change,
since this is a phishing-detection/security-related project — see
`SECURITY.md` for the project's security posture and reporting process,
and `reports/FINAL_REPORT.md` for the evaluation methodology this
project uses before accepting a model/data change (diagnose before
fixing, evaluate old vs. new on identical held-out data, check for
regressions before adopting a change).

## Questions

**Naman Khatak** — namankhatak@gmail.com
