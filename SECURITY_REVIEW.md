# [PROJECT_NAME] — Security Review

**Date**: 2026-08-11
**Scope**: `extension/` (Manifest V3 Chrome extension) and `src/phishshield/api/` (FastAPI backend). Research/data pipeline code (`data/`, `models/`, `features/`) is out of scope — it runs offline, never handles untrusted network input, and is not part of the shipped product surface.

**Method**: direct code review (not automated static analysis) plus one real, run-not-simulated dependency scan (`pip-audit`, output below). No penetration testing was performed against a deployed instance, because nothing is deployed yet.

---

## Findings

### HIGH (blocked, not fixable right now — see below)

**H1 — `starlette` has known CVEs; no fixed version is published yet.**
`pip-audit` (real scan, run 2026-08-11) against this repo's `.venv` found `starlette==0.49.3` (installed transitively via `fastapi>=0.110`) flagged for 5 advisories (`PYSEC-2026-161`, `-248`, `-249`, `-2280`, `-2281`), with the advisory database listing fix versions `1.0.1`–`1.3.1`.

**Attempted fix, 2026-08-11**: confirmed directly (`pip index versions starlette`/`fastapi`, and `pip install --upgrade starlette fastapi`, which reported "already satisfied") that **`0.49.3`/`0.128.8` are the latest versions of `starlette`/`fastapi` currently published on PyPI** — there is no `starlette 1.x` release to install. The advisory database's fix-version metadata points at a version that doesn't exist yet on PyPI as of this check. This isn't a case of "didn't bother upgrading" — there is nothing newer to upgrade *to* right now.

**Action before any public deployment**: re-run `pip-audit` and `pip index versions starlette` periodically (this is a "when it ships" item, not a "when I get to it" item) — once `starlette>=1.0.1` is actually published, `pip install --upgrade starlette fastapi && pytest -q` and confirm the advisories clear. Tracked as blocked-on-upstream, not resolved.

### MEDIUM

**M1 — Wildcard CORS is still the default (guarded, not eliminated).**
`config.py`'s `PHISHSHIELD_CORS_ORIGINS` defaults to `"*"`, and `app.py` only refuses to start with `*` when `PHISHSHIELD_ENV=production` is explicitly set (see `bfabb89`). If a production deployment forgets to set `PHISHSHIELD_ENV=production`, wildcard CORS will silently ship. **Mitigation already in place**: the guard exists and is tested (`test_production_refuses_wildcard_cors`); **residual risk**: it depends on the deployer setting the env var, which is a manual step (see `LOCAL_SETUP.md`/deployment docs — must explicitly call this out at deploy time, not just in code).

**M2 — Rate limiter and body-size cap are single-instance, in-memory.**
Documented plainly in `middleware.py`'s docstring: `RateLimitMiddleware`'s counters live in process memory. A multi-instance deployment (e.g. Render/Cloud Run autoscaling to N instances) would have each instance enforce the limit independently, effectively multiplying the real limit by N. Not a vulnerability at v1's expected single-small-instance scale, but a real gap if the service scales horizontally later without also moving to a shared store (Redis, etc.).

**M3 — No authentication on `/analyze`.**
Anyone who can reach the deployed API can call `/analyze` (rate-limited, size-capped, but not authenticated). Acceptable for a free public-facing analysis endpoint with no user accounts or paid resources behind it (matches the product's actual shape — a stateless classifier call, no PII, no billing), but worth stating explicitly as a decision, not an oversight: no API keys are issued, no per-user quota exists beyond the global per-IP rate limit.

### LOW

**L1 — Health-check exemption from rate limiting is path-based, not method-scoped.**
`RateLimitMiddleware` exempts any request to `/health` regardless of HTTP method. `/health` only has a `GET` handler registered in FastAPI, so a `POST /health` would 405 before reaching application logic either way — low practical risk, noted for completeness.

**L2 — `get_model_version()` exposes a content hash, not a path — verified, not just claimed.**
Explicitly checked: `GET /health`'s `model_version` field is `hashlib.sha256(...).hexdigest()[:12]`, never the artifact's filesystem path. Confirmed via `test_health_reports_model_loaded_and_a_stable_version`'s assertion that no `/` or `\` appears in the returned value.

**L3 — `/analyze`'s 503 error message includes a relative filesystem path when the model artifact is missing** (`model_store.py`'s `_MISSING_ARTIFACT_HINT`, e.g. `"artifacts/phishing_classifier.joblib not found..."`). This is a relative path within the repo, not an absolute filesystem path, contains no secrets, and is genuinely useful for whoever is running the API locally to fix the problem. Judged acceptable for this project's scope (a local/small-deployment research tool, not a service where path disclosure meaningfully aids an attacker), but noted since the Phase 9 mega-prompt specifically asked to check for this.

### INFO (no action needed, noted for completeness)

**I1 — No `background.js`, no `chrome.runtime` message passing.** The extension has no persistent background script and no cross-context messaging channel (popup talks directly to the injected content-script functions via `chrome.scripting.executeScript`'s return value, and to the backend via `fetch`). This is a smaller attack surface than a typical extension architecture — there's no message-passing surface to spoof or intercept between extension contexts.

**I2 — No `eval`, no `new Function`, no remotely-loaded scripts.** Verified via direct grep across `extension/*.js` and `extension/*.html` — zero matches for `eval(`, `new Function(`, or a `<script src="http...">`. All extension code ships in the package; nothing is fetched and executed at runtime.

**I3 — `innerHTML` usage is a single, safe, constant-only clear.** The only `innerHTML` assignment in the extension (`popup.js`: `reasonsEl.innerHTML = ""`) sets a literal empty string to clear a list before repopulating it via `createElement`/`textContent`. No API-derived string is ever assigned to `innerHTML` or interpreted as markup — verified by grep across both `popup.js` and `page_overlay.js`; every dynamic value (risk label, reasons, URL, title) goes through `textContent` only. This was a deliberate design constraint from when the overlay was built, not an accidental gap — see `extension/page_overlay.js`'s file header.

**I4 — Shadow DOM used with `mode: "closed"` for the warning overlay.** Isolates the overlay's DOM from page scripts (a malicious page script cannot query into `document.getElementById("phishshield-overlay-host").shadowRoot` to read or tamper with the warning's contents, since `closed` mode doesn't expose `.shadowRoot`). Verified against `page_overlay.js`.

**I5 — No prototype pollution surface identified.** The extension never does a recursive/deep merge of untrusted JSON into an object it later uses for property lookups (the classic prototype-pollution vector) — `popup.js` destructures the API response into named fields (`verdict.risk_score`, `verdict.reasons`, etc.) rather than spreading or merging it into a shared object.

**I6 — Backend input validation is Pydantic-enforced, not hand-rolled.** `AnalyzeRequest.features: Optional[Dict[str, float]]` rejects non-numeric feature values at the framework level before any application code runs; `predict_feature_dict()` additionally reindexes to the model's known columns with `fill_value=0.0`, so unexpected extra keys are silently dropped rather than causing a type error or being passed through uninspected.

**I7 — No secrets found in the extension bundle or backend source.** Grepped `extension/*.js`, `extension/*.json`, and the API source for API-key/secret/token/password patterns — no matches (consistent with the architecture: the extension never holds credentials, and the only external API keys in this project — Gemini/Anthropic, for the offline dataset-generation pipeline — live in `.env`, which is gitignored and never read by `api/` or `extension/` code).

---

## Real `pip-audit` scan output (2026-08-11, this repo's `.venv`)

39 advisories found across 11 packages. Most are in packages this project doesn't import directly (`pillow`, `msgpack`, `click`, `filelock` — transitive dependencies of dev/plotting tools like `matplotlib`/`pytest`, not the deployed API's runtime path). The ones that matter for the deployed API surface:

| Package | Installed | Advisories | Fix |
|---|---|---|---|
| `starlette` | 0.49.3 | 5 (see H1) | 1.0.1–1.3.1 |
| `python-dotenv` | 1.2.1 | 1 | 1.2.2 |
| `requests` | 2.32.5 | 1 | 2.33.0 |
| `urllib3` | 2.6.3 | 2 | 2.7.0 |
| `setuptools` | 58.0.4 | 4 | up to 83.0.0 |
| `pip` | 26.0.1 | 3 | 26.1.2 |

`requests`/`urllib3` are pulled in by the (offline, dataset-generation-only) `llm`/`gemini` optional dependency groups, not the core `/analyze` request path — lower priority than `starlette`. Full raw output available by re-running `pip-audit` in the project venv; not pasted in full here to keep this document scannable.

---

## Fixed in this pass (not just found)

- CORS lockdown mechanism (guard against wildcard CORS in production) — `bfabb89`
- Rate limiting + request size cap — `bfabb89`
- `innerHTML`-free dynamic rendering (was already the case from the Phase 9 UX rebuild, re-verified here rather than assumed)
- Model artifact fails loudly instead of silently falling back to a lower-quality model — this was itself a real bug found and fixed earlier in this project (see `PROJECT_BRIEF.md`, Phase 6)

## Not fixed in this pass — action required before public deployment

1. **H1**: blocked on upstream, not on effort — confirmed 2026-08-11 that `starlette 0.49.3`/`fastapi 0.128.8` are the latest versions on PyPI; no fixed release exists to install yet. Re-check `pip index versions starlette` periodically and upgrade the moment `>=1.0.1` ships.
2. Set `PHISHSHIELD_ENV=production` and a real `PHISHSHIELD_CORS_ORIGINS` value as a **required** step in the deployment checklist (see `LOCAL_SETUP.md`/Render config docs) — the code enforces this, but the human deploying it still has to actually set it.
3. If usage ever grows past a single small instance, replace the in-memory rate limiter (M2) with a shared store.
