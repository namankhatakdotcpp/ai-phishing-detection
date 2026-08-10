# PhishShield AI — Privacy Policy

**Last updated**: 2026-08-11
**Status**: research prototype, not yet published to the Chrome Web Store.

This document describes what the current, actual implementation does —
verified against the source code in this repository, not aspirational.
If you find a discrepancy between this document and the code, the code
is what actually runs; please treat that as a bug in this document and
report it.

## What triggers analysis

PhishShield AI **never** reads or analyzes any page automatically or in
the background. Analysis of the current browser tab happens **only**
when you click the extension icon and then click "Analyze this page."
This uses Chrome's `activeTab` permission, which grants the extension
temporary access to the current tab only after that explicit click —
not standing access to any site you visit.

## What is collected and transmitted

When you click "Analyze this page," the extension (`page_extractor.js`,
running in the current tab) reads:

- The page's URL and title.
- Structural counts and attributes: number of `<form>` elements, number
  of password/text/email input *fields* (their presence and type, never
  their contents), number of `<iframe>` elements, the domains referenced
  by external `<script src>` and `<form action>` attributes, and whether
  any element has an inline `display:none`/`visibility:hidden` style.

This numeric/textual structural summary — never the page's full HTML,
never a screenshot, never anything else on the page — is sent over HTTPS
(or `http://127.0.0.1` for local development) to the PhishShield backend
for scoring, and nothing else is transmitted.

## What is NOT collected, ever

The extension's code contains no logic to read or transmit:

- Passwords, usernames, or any text typed into a form field.
- Cookies, session tokens, or local storage contents.
- Keystrokes.
- Credit card or other payment information.
- Your browsing history (the extension only ever sees the single tab you
  explicitly asked it to analyze, in the moment you asked).
- The page's full HTML or a rendered screenshot.

This is a code-level guarantee, not a policy promise layered on top of
code that could do otherwise: `page_extractor.js` never reads any
`.value` property of an input element, and grep-verified (see
`SECURITY_REVIEW.md`) to contain no code path that could.

## What the backend does with the data

The PhishShield backend (`src/phishshield/api/`) receives the structural
feature summary described above, runs it through a trained classifier
and a rule-based explainability layer, and returns a risk score, a
risk band (LOW/SUSPICIOUS/HIGH), and a list of human-readable reasons.
It does not store this data beyond the lifetime of that single request —
there is no database, no user account, and no request history feature
in the current implementation. Server logs record only the HTTP method,
path, response status, and latency in milliseconds for operational
monitoring — never the request body, the feature values, or the URL you
analyzed (see `api/app.py`'s `log_latency` middleware).

## Third parties

None. The backend does not call any third-party API, analytics service,
or advertising network as part of handling an `/analyze` request. (A
separate, offline part of this project uses LLM provider APIs — Gemini/
Anthropic — to generate research *training data*; that code path is
never invoked by the extension or the live `/analyze` endpoint and
involves no data from your browsing.)

## Data retention

None beyond the single request/response cycle described above.

## Your control

Uninstalling the extension, or simply not clicking "Analyze this page,"
stops all data collection immediately and completely — there is no
background process, scheduled task, or persistent listener left running.

## Local vs. deployed backend

As of this writing, the backend runs locally on your own machine
(`127.0.0.1`) — nothing leaves your computer. If a hosted version is
deployed in the future (see `DEPLOYMENT.md`), this document will be
updated to reflect the deployed URL and hosting provider before that
version is distributed, per this project's stated norm of never making
privacy claims the code doesn't support.

## Contact

`[contact email placeholder — fill in before Web Store submission]`
