// Single place to switch the extension between local development and a
// deployed production backend. Edit API_BASE below (and
// manifest.json's host_permissions to match) when pointing at a real
// deployed API -- see DEPLOYMENT.md "Switch the extension over".
//
// No build step in this extension (plain unpacked files), so this is a
// plain global rather than an env-var-driven bundler config -- keeps
// "which backend am I talking to" a one-line, obviously-named edit
// instead of a hardcoded value buried in popup.js's request logic.

const PHISHSHIELD_CONFIG = {
  // Production (Render). Verified 2026-08-12: /health and /analyze both
  // confirmed against real fixtures, scores byte-identical to local
  // (Wells Fargo 6/100 LOW, PayPal fixture 87/100 HIGH), CORS restricted
  // to this extension's dev-mode origin -- see DEPLOYMENT.md.
  API_BASE: "https://phishshield-api-urkx.onrender.com",

  // Local development (uncomment to switch back -- requires `uvicorn
  // phishshield.api.app:app --port 8000` running on this machine, see
  // LOCAL_SETUP.md; also re-add the localhost origins to manifest.json's
  // host_permissions if they were removed):
  // API_BASE: "http://127.0.0.1:8000",
};
