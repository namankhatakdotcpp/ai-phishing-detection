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
  // Local development (default). Requires `uvicorn phishshield.api.app:app
  // --port 8000` running on this machine -- see LOCAL_SETUP.md.
  API_BASE: "http://127.0.0.1:8000",

  // Production example (uncomment and edit once deployed -- see
  // DEPLOYMENT.md for exact settings; also add the real origin to
  // manifest.json's host_permissions, since the localhost entries won't
  // match a deployed HTTPS origin):
  // API_BASE: "[PRODUCTION_API_URL]",
};
