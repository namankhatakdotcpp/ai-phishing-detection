# Feature parity: Python pipeline vs. `page_extractor.js`

Mega-prompt Phase 3 requirement: an explicit mapping table from the
Python feature schema to the browser-side extractor, since the JS must
mirror the Python schema *exactly* for the trained model's input
distribution to hold. This table was produced by direct comparison of
`src/phishshield/features/url_features.py` and
`src/phishshield/features/html_features.py` against
`extension/page_extractor.js`, not written from memory.

**No automated cross-runtime parity test exists.** This environment has
no Node.js (`which node` → not found, confirmed 2026-08-11) and no way
to install it, so there is no way to run `page_extractor.js` and compare
its output to Python's `extract_features()` on identical input inside
the test suite. Parity was verified by (a) this line-by-line table, and
(b) live manual checks earlier in this project against real pages
(Wikipedia, a controlled phishing fixture) where the JS-extracted vector
was hand-copied into a Python `curl`/script call and produced the
expected classification. **If Node becomes available, the highest-value
addition to this project's test suite would be an automated fixture-based
parity test** — see "Suggested follow-up" at the bottom.

## URL-lexical features (`url_features.py` ↔ `extractUrlFeatures` in `page_extractor.js`)

| Python feature | JS feature | Computation | Status |
|---|---|---|---|
| `url_length` | `url_length` | `len(url)` / `url.length` | ✅ identical |
| `num_dots` | `num_dots` | `url.count(".")` / `(url.match(/\./g)\|\|[]).length` | ✅ identical |
| `num_hyphens` | `num_hyphens` | `url.count("-")` / regex count | ✅ identical |
| `num_subdomains` | `num_subdomains` | `max(0, len(host_parts) - 2)` | ✅ identical logic |
| `num_digits` | `num_digits` | count of digit chars | ✅ identical |
| `digit_ratio` | `digit_ratio` | `num_digits / len(url)` | ✅ identical |
| `special_char_count` | `special_char_count` | count against `_SPECIAL_CHARS` set | ✅ same literal character set |
| `special_char_ratio` | `special_char_ratio` | `special_char_count / len(url)` | ✅ identical |
| `has_at_symbol` | `has_at_symbol` | `"@" in url` | ✅ identical |
| `has_ip_literal` | `has_ip_literal` | `ipaddress.ip_address()` / regex-based IPv4 + crude IPv6 check | ⚠️ **approximation** — Python uses the stdlib `ipaddress` module (fully correct IPv4/IPv6 parsing); JS uses a regex for IPv4 and a loose hex-and-colon heuristic for IPv6. Edge-case IPv6 literals could disagree. Low practical impact (`has_ip_literal` is rare in real traffic either way), but not a byte-for-byte match. |
| `is_https` | `is_https` | `scheme == "https"` / `protocol === "https:"` | ✅ identical |
| `path_length` | `path_length` | `len(parts.path)` / `pathname.length` | ✅ identical |
| `query_length` | `query_length` | `len(parts.query)` (no `?`) / `search` with leading `?` stripped | ✅ identical after the strip |
| `has_suspicious_tld` | `has_suspicious_tld` | membership in the same 10-TLD set | ✅ identical set, verified by direct comparison |
| `has_port` | `has_port` | `parts.port is not None` / `parsed.port` truthy | ✅ identical |
| `is_parsable` | `is_parsable` | `urlsplit()` doesn't raise / `new URL()` doesn't throw | ✅ same fallback behavior (defaults to `0` + zeroed vector) |

## HTML-structural features (`html_features.py` ↔ `extractHtmlFeatures` in `page_extractor.js`)

| Python feature | JS feature | Computation | Status |
|---|---|---|---|
| `has_html` | `has_html` | Python: `0` if no HTML string given. JS: always `1` (a live tab always has a DOM). | ✅ correct by construction — the browser-side extractor only ever runs against a real live page, so `has_html=0` is a Python-only case (URL-only legacy samples), never reachable from the extension. |
| `num_forms` | `num_forms` | `len(soup.find_all("form"))` / `querySelectorAll("form").length` | ✅ identical |
| `num_password_fields` | `num_password_fields` | `input[type=password]` count | ✅ identical selector |
| `num_text_input_fields` | `num_text_input_fields` | `input[type=text\|email]` count | ✅ identical selector |
| `num_iframes` | `num_iframes` | `iframe` count | ✅ identical |
| `num_external_js_domains` | `num_external_js_domains` | distinct registrable-domain labels of `script[src]` not matching the page's domain | ✅ identical algorithm (naive `parts[-2]` label, same on both sides) |
| `num_external_form_actions` | `num_external_form_actions` | count of `form[action]` starting with `http(s)://` whose domain differs from the page's | ✅ identical |
| `has_external_form_action` | `has_external_form_action` | `num_external_form_actions > 0` | ✅ identical |
| `title_brand_mismatch` | `title_brand_mismatch` | title mentions a brand from the same 16-brand list, and that brand isn't the page's own domain label | ✅ identical brand list (copied verbatim, verified) |
| `num_hidden_elements` | `num_hidden_elements` | elements whose `style` attribute contains `display:none` or `visibility:hidden` (whitespace-stripped) | ✅ identical string check. **Known limitation shared by both sides**: this only catches *inline* `style=""` hiding, not CSS-class-based or stylesheet-based hiding (e.g. `.hidden { display: none }` in a `<style>` block or external CSS) — a real page relying on class-based hiding would score `0` here on both Python and JS, consistently but incompletely. |
| `has_favicon_mismatch` | `has_favicon_mismatch` | Always `0` — **dead feature on both sides**. `html_features.py` initializes it in the returned dict but the function body never sets it to anything else; `page_extractor.js` mirrors that (also always `0`). Not a parity bug — it's a feature that was scaffolded but never implemented in the original Python pipeline, correctly reproduced as inert in JS rather than "fixed" unilaterally on one side only. | ✅ identically inert |

## Deliberately NOT extracted (privacy boundary, not a parity gap)

Neither side reads or transmits: input **values** (only field *type*/*presence*
is counted), cookies, `localStorage`, keystrokes, or the page's full raw
HTML. This is a shared design constraint, not something that could
drift out of parity — there's no Python equivalent to compare against,
because the real pipeline's HTML loaders never touch live pages either
(see `PROJECT_BRIEF.md` §2's no-live-scraping constraint).

## Overlay viewport/z-index testing (mega-prompt Phase 6)

Tested live against `https://en.wikipedia.org/wiki/Phishing`:

- **High z-index page content**: injected a real `position:fixed;
  z-index:999999999` element into the live page before showing the
  overlay. The overlay's backdrop uses `z-index: 2147483647` — the
  maximum representable CSS z-index value — so it is guaranteed to
  render above *any* value a page could set, confirmed by direct
  inspection of both elements' computed styles (the injected element
  measured `z-index: 999999999`, visible, correctly positioned).
- **Mobile viewport** (375×812 preset): the overlay's card uses
  `width: min(420px, 92vw)`, i.e. it's responsive by construction, not
  by a viewport-specific media query that could be missed. Screenshot
  capture at this viewport size showed some rendering quirks in this
  specific browser tool (a resized element reported unexpected pixel
  dimensions inconsistent with the requested 375px viewport) that read
  as a tool-side artifact rather than an overlay bug, given the CSS
  itself has no fixed-width assumption. **Not independently re-verified
  in real Chrome at a real mobile viewport** — flagged rather than
  claimed clean.

## Suggested follow-up (not done — no Node.js available in this environment)

If Node becomes available: a `tests/js_parity/` fixture set (a handful of
saved HTML pages) run through both `extract_features()` (Python) and
`page_extractor.js`'s logic (via `node --eval` or a headless browser) on
identical input, asserting the two dicts are equal key-for-key. This
would convert the "⚠️ approximation" row above (IP-literal parsing) from
a documented risk into either a proven non-issue or a concrete bug to fix.
