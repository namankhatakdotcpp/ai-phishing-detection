# Local setup — backend + extension

Everything below runs entirely on your machine against `127.0.0.1`. No
account, payment, or network service is required for local use.

## 1. Backend

```bash
git clone <this repo>   # or cd into it if you already have it
cd [PROJECT_NAME]       # repo root — wherever pyproject.toml lives
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

The demo API needs the trained model artifact at
`artifacts/phishing_classifier.joblib`. If it's already committed in your
checkout, skip to starting the server. If it's missing (`GET /health`
will report `model_loaded: false`), regenerate it — this requires the
real datasets described in `PROJECT_BRIEF.md` §Phase 1/9 to be present
under `data/raw/`/`data/generated/`:

```bash
python -m phishshield.models.export_demo_model \
  --phishtank data/raw/phishtank.csv \
  --openphish data/raw/openphish.txt \
  --tranco data/raw/tranco.csv --tranco-limit 5000 \
  --tranco-html data/generated/tranco_benign_html.jsonl \
  --llm-generated data/generated/llm_phishing_v1.jsonl
```

Start the server:

```bash
python -m uvicorn phishshield.api.app:app --host 127.0.0.1 --port 8000
```

Verify it's actually up and the real model loaded (don't skip this):

```bash
curl -s http://127.0.0.1:8000/health
# expect: {"status":"ok","model_loaded":true,"model_version":"<12-char-hash>"}
```

If `model_loaded` is `false`, the server is running but has no model —
`/analyze` will return `503` until you generate the artifact above.

## 2. Extension

1. Open Chrome, go to `chrome://extensions`.
2. Enable **Developer mode** (top-right toggle).
3. Click **Load unpacked**, select this repo's `extension/` directory.
4. Navigate to any `http://` or `https://` page.
5. Click the [PROJECT_NAME] icon in the toolbar, then **Analyze this
   page**.

You should see a LOW/SUSPICIOUS/HIGH risk card. For a HIGH result, an
in-page warning overlay also appears on the page itself.

**If the popup says it can't reach the backend**: confirm step 1's
server is still running and `curl http://127.0.0.1:8000/health` responds
— the extension's `host_permissions` are scoped to
`127.0.0.1:8000`/`localhost:8000` only, so it cannot reach a backend
running anywhere else without a manifest change (see
`extension/manifest.json`, and Phase 12 of the production plan for
switching to a deployed HTTPS URL).

## 3. Running the test suite

```bash
pytest -q --ignore=tests/live
```

`tests/live/` makes real, paid calls to LLM provider APIs and is skipped
unless you explicitly opt in (requires `.env` with a real key — see
`.env.example`). Never required for normal development.

`tests/test_js_parity.py` (runs the real `extension/page_extractor.js`
against Python's feature pipeline via Node + jsdom — see
`FEATURE_PARITY.md`) is also skipped gracefully if Node.js isn't set up.
To enable it:

```bash
# Install Node.js (any recent LTS) if you don't have it -- this project's
# own dev environment had no package manager available at all, so Node
# was downloaded directly from nodejs.org and extracted (no sudo/admin
# needed):
#   curl -L https://nodejs.org/dist/v24.19.0/node-v24.19.0-darwin-arm64.tar.gz \
#     | tar -xz -C ~/.phishshield-node --strip-components=1
#   export PATH="$HOME/.phishshield-node/bin:$PATH"   # add to your shell rc to persist
# Or use your platform's usual method (Homebrew, nvm, the official
# installer from nodejs.org) if available.

cd tests_js && npm install && cd ..
pytest -q tests/test_js_parity.py
```

## 4. Environment variables (all optional for local use)

See `.env.example`. Everything under "Demo API" has a safe default and
only matters for production deployment — copy `.env.example` to `.env`
if you want to override any of them locally, but you don't need to for
the steps above to work.

## Known local-only limitations

- The demo model (`artifacts/phishing_classifier.joblib`) has a real,
  measured ~21.7% false-positive rate on the classifier alone (~7.7%
  with judge fusion) — see `reports/FINAL_REPORT.md` §5-6. Expect
  occasional SUSPICIOUS/HIGH verdicts on genuinely benign pages; this is
  a stated research finding, not a setup bug.
- CORS defaults to `*` locally (see `SECURITY_REVIEW.md` M1) —
  intentional for zero-friction local development, never acceptable for
  a public deployment (see Phase 11 deployment docs).
