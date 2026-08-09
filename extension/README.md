# PhishShield AI — demo extension

A thin Manifest V3 popup UI over the Phase 6 demo API. It only ever scores
one of a curated, fixed list of demo samples returned by the backend's
`GET /demo-samples` — it never reads or scans the page you're currently on
(no `activeTab`, `scripting`, or broad `host_permissions` are requested;
`host_permissions` is scoped to `localhost:8000`/`127.0.0.1:8000` only).

## Run it

1. Start the backend from the repo root:

   ```bash
   source .venv/bin/activate
   uvicorn phishshield.api.app:app --port 8000
   ```

2. In Chrome, go to `chrome://extensions`, enable "Developer mode", click
   "Load unpacked", and select this `extension/` directory.
3. Click the PhishShield AI icon, pick a demo sample, and click "Analyze".

## Files

- `manifest.json` — MV3 manifest, minimal permissions
- `popup.html` / `popup.css` / `popup.js` — the popup UI; `popup.js` calls
  `GET /demo-samples` and `POST /analyze` on the local backend only
