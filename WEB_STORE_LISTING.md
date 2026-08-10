# Chrome Web Store listing draft

**Status**: draft only. Do not submit until `DEPLOYMENT.md`'s Phase 12
(pointing the extension at a real deployed HTTPS backend) is complete —
a Web Store listing pointing at `localhost` is not usable by anyone but
the developer.

## Packaging (verified — actually run, not just written)

```bash
python scripts/package_extension.py
```

Builds `release/` with exactly the 6 files Chrome needs (`manifest.json`,
`popup.html`/`.css`/`.js`, `page_extractor.js`, `page_overlay.js`),
validates no backend code/secrets/dataset paths leaked in, and zips it
to `phishshield-extension.zip` at the repo root (this file and
`release/` are gitignored — regenerate, don't hand-edit). Confirmed
working: last run packaged 6 files into a 10,299-byte zip with zero
validation failures.

## Extension name

PhishShield AI

## Category recommendation

Productivity, or Security (if Chrome's current taxonomy has a
security-specific category — check at submission time, Chrome's
category list changes).

## Short description (≤132 characters, Chrome's current limit — verify at submission time)

> Analyzes the page you're on for phishing indicators, on your request. No passwords, forms, or history collected.

## Detailed description

> PhishShield AI is a research-grade phishing detector you control. Click
> the icon, click "Analyze this page," and get a LOW / SUSPICIOUS / HIGH
> risk assessment with plain-language reasons — built from a classifier
> trained on real phishing data and an explainability layer, not a
> black-box score.
>
> **What it looks at**: the page's URL patterns and structural signals —
> form and password-field counts, where forms submit data, external
> scripts, and similar. **What it never looks at**: what you type, your
> passwords, your cookies, or your browsing history. It only ever
> analyzes the one tab you explicitly ask it to, in the moment you ask.
>
> For high-risk pages, PhishShield shows an in-page warning before you
> interact further, with the option to leave or continue at your own
> discretion.
>
> **This is a research prototype from an academic project** — treat its
> verdicts as one input to your own judgment, not a guarantee. See the
> full methodology and known limitations at
> `[project report URL placeholder]`.

## Single-purpose description

(Same as `WEB_STORE_PRIVACY_ANSWERS.md`'s — Chrome requires consistency
between the two.)

> Analyzes the structural characteristics of the current web page —
> only when the user explicitly clicks "Analyze this page" — and shows
> a phishing-risk assessment with explanations.

## Permission justifications

(See `WEB_STORE_PRIVACY_ANSWERS.md` for the full text — Chrome's listing
form typically wants a short version per permission.)

- `activeTab` — read the current tab only after the user's explicit click.
- `scripting` — inject the feature-extraction and warning-overlay scripts into that tab.
- `host_permissions` (deployed API origin) — call the backend that scores the page.

## Data-use explanation (short form for the listing page)

> Collects only structural page metadata (form counts, external script/
> form domains, URL, title) when you click Analyze. Never collects
> passwords, form values, cookies, or browsing history. See our privacy
> policy for the full list.

## Privacy policy URL

`[placeholder — same as WEB_STORE_PRIVACY_ANSWERS.md]`

## Screenshot checklist (capture these once the deployed version is running)

1. Popup showing a LOW-risk result on a real benign page.
2. Popup showing a HIGH-risk result with the reasons list expanded.
3. The in-page warning overlay on a controlled phishing test page (use a
   fixture, never a real live phishing site — matches this project's own
   no-live-scraping ethical constraint).
4. Popup's "View details" panel showing classifier/judge scores.
5. The extension icon in the Chrome toolbar for context.

Chrome's current size/format requirements for screenshots change
periodically — check the Developer Dashboard's upload requirements at
submission time rather than assuming a fixed size here.

## Icon

Not yet created — `extension/` has no `icons/` directory in this
checkout. Required before submission: a set of icon sizes per Chrome's
current manifest icon requirements (commonly 16/48/128px, verify at
submission time), referenced from `manifest.json`'s `icons` key (not yet
present — currently the extension only sets `action.default_title`
without a custom icon, which is fine for local unpacked testing but not
for a Store listing).
