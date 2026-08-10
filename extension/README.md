# PhishShield AI — v1 security-assistant extension

A Manifest V3 extension over the Phase 9 demo API. Analyzes the
**current tab's** structural features (form/password-field counts,
external script/form-action domains, URL-lexical patterns) against a
local PhishShield AI backend, but only when you click "Analyze this
page" — no persistent background scanning, no `<all_urls>` access.

Uses `activeTab` + `scripting`, Chrome's narrower alternative to broad
host permissions: access is granted only after the user's explicit
click, only for that tab, only until the popup closes. `host_permissions`
stays scoped to `localhost:8000`/`127.0.0.1:8000` (the local backend) —
the extension never gets standing access to the pages it analyzes.

**Privacy**: `page_extractor.js` only reads page *structure* — element
counts, attribute strings (`action`, `src`, inline `style`), the page
title, and the URL. It never reads input *values*, so no password,
username, or other form content a user has typed is ever collected or
sent to the backend. See its file header for the exact contract. The
in-page warning overlay (`page_overlay.js`) renders all dynamic text
(risk label, reasons) via `textContent` only, never `innerHTML`, so a
compromised or malformed backend response can never be interpreted as
markup/script.

## The real model, not a toy

`/analyze` is backed by `artifacts/phishing_classifier.joblib` — the
same classifier trained on real PhishTank/OpenPhish/Tranco + fetched
benign HTML + real LLM-generated data, loaded once at API startup (see
`api/model_store.py`; fails loudly with a fix-it message if the artifact
is missing rather than silently falling back to a lower-quality model —
that's exactly how an earlier synthetic-only demo model's backwards
verdicts went unnoticed). Fusion weight is `alpha=0.7` (`api/app.py`),
matching the value the real alpha sweep validated (see
`reports/FINAL_REPORT.md`).

## Run it

1. Start the backend from the repo root:

   ```bash
   source .venv/bin/activate
   uvicorn phishshield.api.app:app --port 8000
   ```

   Check `GET /health` reports `model_loaded: true` before continuing.

2. In Chrome, go to `chrome://extensions`, enable "Developer mode", click
   "Load unpacked", and select this `extension/` directory.
3. Navigate to any `http(s)://` page, click the PhishShield AI icon, and
   click "Analyze this page".

Non-`http(s)` pages (`chrome://`, the Chrome Web Store, PDF viewer, etc.)
can't be analyzed — Chrome doesn't allow script injection there, and the
popup disables the button and says so rather than silently failing.

## What you'll see

- **LOW / SUSPICIOUS / HIGH** risk card in the popup, reusing the
  backend's own `judge.risk_band()` thresholds (never recomputed
  client-side) -- "medium" is labeled "SUSPICIOUS" in the UI only.
- For **HIGH**-risk pages, an in-page warning overlay (Shadow DOM, sits
  above the page, immune to the site's own CSS) with "Leave website" /
  "Continue anyway". "Continue anyway" is remembered for the rest of
  that tab's session (cleared on navigation/reload) so re-analyzing
  doesn't re-interrupt a choice you already made.
- The popup's "View details" reveals the raw classifier/judge scores
  behind the fused risk score.

## Files

- `manifest.json` — MV3 manifest; `activeTab` + `scripting` only, no
  broad host permissions
- `page_extractor.js` — injected into the active tab on click; computes
  the same feature schema as `phishshield.features.url_features` /
  `html_features` client-side, in JS, so the vector sent to the backend
  matches the trained model's input distribution
- `page_overlay.js` — injected only after a HIGH verdict from the same
  click; builds the in-page warning inside a closed Shadow DOM
- `popup.html` / `popup.css` / `popup.js` — the popup UI; `popup.js`
  extracts the current tab's features, calls `POST /analyze` on the
  local backend only (feature vector, never raw HTML or form values),
  renders the risk card, and triggers the overlay for HIGH verdicts

## Known limitations

- **FPR on real data is real, not hidden**: the classifier alone has a
  measured ~21.7% false-positive rate on held-out real benign pages;
  judge fusion (`alpha=0.7`) brings that to ~7.7%. Expect occasional
  SUSPICIOUS/HIGH verdicts on genuinely benign pages -- this is stated
  plainly in `reports/FINAL_REPORT.md`, not smoothed over here.
- **Local backend only**: `API_BASE` in `popup.js` points at
  `127.0.0.1:8000`. Pointing it at a deployed HTTPS backend, adding
  request rate limiting, and locking down CORS (`api/app.py` currently
  allows `*` origins, fine for local-only use) are Sprint 2 items, not
  done yet.
- **Feature space is structural, not semantic**: per
  `reports/FINAL_REPORT.md` Section 3.2/6, the model has no channel onto
  page *content* quality (persuasive copy, brand voice) -- only URL and
  DOM structure. It can't reason about whether text on the page reads as
  a convincing impersonation.
