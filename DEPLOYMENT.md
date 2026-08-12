# Production deployment — exact settings

**Status: deployed and verified.** The backend described below (Option
A, Render) is live at `https://phishshield-api-urkx.onrender.com`,
serving the frozen v4 model (`b6ed9eef36cd`). Production `/health` and
`/analyze` have been verified directly (not just assumed from a
successful build), CORS was verified restrictive (not wildcarded), and
the Chrome extension has been switched over (`extension/config.js`) and
validated with a full live-Chrome pass against this exact URL — see
`reports/FINAL_REPORT.md` §8.2 for the complete verification record.
This file is kept as the reference for the exact settings used and for
reproducing/redeploying, not as a "not yet done" notice anymore.

**Model-quality context**: the deployed v4 model reached **0% FPR on a
domain-disjoint 28-page generalization set**, zero HIGH/MEDIUM false
positives, with no measured phishing-recall cost — see
`reports/FINAL_REPORT.md` §3.13 for the full v3-vs-v4 evaluation and
§8.1 for the current, detailed release gate (Docker and a formal
calibration correction remain open, neither blocking this project's
actual deployment).

**One real bug found and fixed during this deployment**: the first
Render attempt failed `/health` with `ModuleNotFoundError: No module
named '_loss'` — a scikit-learn cross-version pickle-compatibility
issue (the artifact was serialized with 1.6.1 locally; `requirements.txt`
had `scikit-learn>=1.3` unpinned, so Render could resolve a different
version). Fixed by pinning `scikit-learn==1.6.1` exactly. See §8.2 for
the full diagnosis.

## Option A: Render (Blueprint, `render.yaml` already in this repo)

1. Push this repo to GitHub (you: `git push`, since this session doesn't
   push without being asked, per its own operating rules).
2. Render dashboard → **New** → **Blueprint** → connect the GitHub repo.
   Render reads `render.yaml` automatically.
3. Render will prompt for the one `sync: false` variable:
   **`PHISHSHIELD_CORS_ORIGINS`** — set to the extension's real origin
   once known (`chrome-extension://<extension-id>`; Chrome assigns the
   ID on Web Store publish, or you can find a dev-mode ID at
   `chrome://extensions` after loading unpacked). Until you have a
   stable ID, a placeholder like `https://example.invalid` is safer than
   leaving it as `*` — the CORS guard in `api/app.py` will refuse to
   start in production with a wildcard regardless, so this step is not
   optional.
4. Click **Deploy**.

**Manual settings, if not using the Blueprint / building by hand:**

| Setting | Value |
|---|---|
| Runtime | Python 3.11 |
| Build command | `pip install -r requirements.txt && pip install -e .` |
| Start command | `uvicorn phishshield.api.app:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |
| `PHISHSHIELD_ENV` | `production` |
| `PHISHSHIELD_CORS_ORIGINS` | the extension's real origin (not `*`) |
| `PHISHSHIELD_RATE_LIMIT_PER_MINUTE` | `60` (adjust to taste) |
| `PHISHSHIELD_MAX_REQUEST_BYTES` | `65536` |

**Expected URL format**: `https://<service-name>.onrender.com` (Render
assigns this; the actual URL is shown in the Render dashboard after
first deploy — record it as `[PRODUCTION_API_URL]`).

**Auto-deploy**: once the GitHub repo is connected (Blueprint or manual
Web Service), Render redeploys automatically on every push to the
connected branch (`main`) by default — no separate deploy step needed
after the initial setup. This can be toggled off in the service's
Settings if you want deploys to require manual approval instead.

**Free-tier limitation — document, don't hide**: Render's free Web
Service plan spins the service down after ~15 minutes of no requests
and wakes it on the next incoming request. The first request after a
period of inactivity will be noticeably slower (a cold start, on the
order of tens of seconds) while the service restarts and reloads the
model artifact. This is fine for a course-project demo, but it means
this is **not** a continuously-warm production API — say so explicitly
in any demo or writeup rather than implying always-on availability.

## Option B: Google Cloud Run (using the committed `Dockerfile`)

**Not built or tested in this session** — no `docker` binary was
available in this environment (verified: `which docker` → not found).
The `Dockerfile` was written from the same verified dependency trace as
`requirements.txt`, but treat it as unverified until you build it once
yourself:

```bash
docker build -t phishshield-api .
docker run -p 8000:8000 phishshield-api
curl http://localhost:8000/health   # verify locally before pushing anywhere
```

Then, once verified locally:

```bash
gcloud run deploy phishshield-api \
  --source . \
  --port 8000 \
  --set-env-vars PHISHSHIELD_ENV=production,PHISHSHIELD_CORS_ORIGINS=<extension-origin>,PHISHSHIELD_RATE_LIMIT_PER_MINUTE=60,PHISHSHIELD_MAX_REQUEST_BYTES=65536 \
  --allow-unauthenticated
```

`--allow-unauthenticated` matches this project's actual auth model (see
`SECURITY_REVIEW.md`, M3 — no auth on `/analyze` by design, a stateless
classifier call with no PII/billing behind it).

**Expected URL format**: `https://phishshield-api-<hash>-<region>.a.run.app`.

## Post-deployment verification (run this yourself after deploying)

```bash
curl -s https://<your-deployed-url>/health
# expect: {"status":"ok","model_loaded":true,"model_version":"<hash>"}

curl -s -X POST https://<your-deployed-url>/analyze \
  -H "Content-Type: application/json" \
  -d '{"features":{"num_password_fields":1,"has_external_form_action":1}}'
# expect a 200 with risk_score/risk_band/reasons
```

If `model_loaded` is `false`, the artifact didn't make it into the
deployed build — check that `artifacts/phishing_classifier.joblib` is
actually committed to the branch/commit Render or Cloud Run built from
(`git ls-files artifacts/`).

## After a successful deployment: switch the extension over

See Phase 12 in `reports/FINAL_REPORT.md`'s plan. Two edits, in one
place each:

1. `extension/config.js` — change `PHISHSHIELD_CONFIG.API_BASE` from
   `http://127.0.0.1:8000` to your deployed HTTPS URL (a commented-out
   production example is already in that file).
2. `extension/manifest.json`'s `host_permissions` — add the new origin
   (the localhost entries can stay for continued local development, or
   be removed for a Store submission — your call).

**Done.** `extension/config.js`'s `API_BASE` points at
`https://phishshield-api-urkx.onrender.com`; `manifest.json`'s
`host_permissions` includes that origin alongside the localhost entries
(kept for continued local development). Validated with a full
live-Chrome pass — see `reports/FINAL_REPORT.md` §8.2.
