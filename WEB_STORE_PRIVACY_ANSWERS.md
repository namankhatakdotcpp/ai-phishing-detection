# Chrome Web Store — Data Use Declaration draft answers

Draft answers for the Web Store Developer Dashboard's "Privacy practices"
tab. Fill these in yourself at submission time (the form UI/wording may
differ slightly from Chrome's current version) — this is a starting
draft grounded in the actual implementation, not a guess at Chrome's
exact form fields.

## Single purpose description

> PhishShield AI analyzes the structural characteristics of the current
> web page (form/input counts, external script and form-submission
> domains, URL patterns) — only when the user explicitly clicks
> "Analyze this page" — and shows a phishing-risk assessment with
> explanations.

## Permission justifications

**`activeTab`**: Required to read the current tab's URL and inject the
structural feature-extraction script, but only after the user's explicit
click — this is the narrower alternative to a standing host permission,
by design.

**`scripting`**: Required to run `page_extractor.js` (feature extraction)
and, for high-risk pages, `page_overlay.js` (the in-page warning) inside
the active tab via `chrome.scripting.executeScript`.

**`host_permissions` (`127.0.0.1:8000`, `localhost:8000` in the
development build)**: Required so the extension can call its own
backend API to score the extracted features. **Must be updated to the
real deployed HTTPS origin before Web Store submission** — a
`localhost`-only host permission is meaningless to a Web Store user
whose machine isn't running the local dev server (see `DEPLOYMENT.md`
Phase 12).

## Data use declarations

| Category | Collected? | Notes |
|---|---|---|
| Personally identifiable information | No | |
| Health information | No | |
| Financial and payment information | No | |
| Authentication information | No | Never reads passwords/credentials — see `PRIVACY_POLICY.md` |
| Personal communications | No | |
| Location | No | |
| Web history | No | Only the single tab explicitly analyzed at the moment of the click; never a history of visited sites |
| User activity | No | No keystroke logging, no click tracking beyond the extension's own UI |
| Website content | **Yes, structural metadata only** | Form/input counts, external script/action domains, URL, page title — never full HTML, never form values. See `PRIVACY_POLICY.md` for the exact list. |

## "Is data sold to third parties?"

No.

## "Is data used for purposes unrelated to the extension's single
purpose?"

No.

## "Is data used to determine creditworthiness or for lending purposes?"

No.

## Privacy policy URL

`[placeholder — host PRIVACY_POLICY.md somewhere public and put the URL here before submission]`
