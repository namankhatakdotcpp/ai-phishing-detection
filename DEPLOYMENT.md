# Production deployment — exact settings

This file is configuration and instructions only. **No deployment has
been performed.** Creating the account, connecting the repo, setting
secrets, and clicking deploy are yours to do (see
`reports/FINAL_REPORT.md`'s final checklist for the exact split).

**Separate, more important gate**: the infrastructure below being ready
does not mean the model is. A real evaluation against 46 real major
websites found 13.0% FPR (`reports/FINAL_REPORT.md` Section 3.7);
subsequent fixes for all three diagnosed causes and a rescale to 130
real pages (Sections 3.8-3.9) brought that to **0.8% FPR at n=130, zero
pages in the HIGH band**, with no measured phishing-recall cost. The
model-quality gate is in materially better shape than earlier revisions
of this file suggested. The remaining blocker is narrower now: live
Chrome validation (an actual unpacked extension in an actual Chrome
profile) has never been run — see Section 8.1's explicit DO NOT DEPLOY
gate. Do not deploy based on this file alone; check Section 3.9 and the
Limitations section first, and actually run the extension in Chrome
before calling this deployment-ready.

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

**Not done yet** — this session doesn't have your deployed URL. `config.js`
exists specifically so this is a one-line change instead of hunting
through `popup.js`'s request logic.
