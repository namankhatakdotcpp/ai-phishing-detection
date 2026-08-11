# Security Policy

[PROJECT_NAME] is an academic research prototype (IIT Mandi ISP course
project) — see `README.md` for the full architecture and
`reports/FINAL_REPORT.md` §8.1 for the current release/deployment gate
status. This policy exists because it's a security-adjacent project,
not because it's presented as a hardened commercial product.

## Scope

The following are within scope for security reports:

- The Chrome extension (`extension/`) — feature extraction, popup UI,
  in-page warning overlay, permissions.
- The backend/API (`src/phishshield/api/`) — request handling, CORS,
  rate limiting, model loading.
- Detection/model behavior — a case where the classifier or judge
  behaves in a way that has real security implications (e.g., a
  systematic bypass, not just "this one page's risk score seems off,"
  which is a model-quality issue better filed as a regular issue).
- Any authentication or security-relevant implementation detail.
- Repository infrastructure, where applicable.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for an undisclosed security
vulnerability.**

Instead, email:

**namankhatak@gmail.com**

Please include:

- A description of the issue.
- Steps to reproduce it.
- Expected behavior vs. actual behavior.
- Potential impact.
- Relevant logs or screenshots, if they can be shared safely (see
  "What NOT to Submit" below).
- A suggested mitigation, if you have one — not required.

## Responsible Disclosure

Please don't publicly disclose an exploitable vulnerability before
there's been a reasonable opportunity to investigate and address it.
Given this is a single-maintainer academic project, "reasonable" may
be longer than for a commercially staffed project — I'll respond as
promptly as I can.

## What NOT to Submit

To keep both the reporter and the project safe:

- Do not submit real people's credentials.
- Do not submit passwords, API keys, session cookies, tokens, personal
  information, or other secrets — redact these from any logs or
  screenshots before sending.
- Do not conduct attacks against third-party websites to demonstrate
  an issue.
- Do not perform credential harvesting, even for demonstration
  purposes.
- Do not distribute real phishing campaigns through this project or
  in a report about it.
- Do not upload malicious files merely to demonstrate a vulnerability
  — describe the issue and, if needed, provide a minimal, clearly
  inert proof of concept instead.

## Security Limitations

This is an academic/course project. It should **not** be treated as a
guaranteed or complete defense against all phishing attacks. As stated
throughout `reports/FINAL_REPORT.md`, the model's claims are narrow and
experimentally scoped — it does not claim 100% detection, does not
claim zero false positives, and is not presented as production-grade
security software. See `README.md`'s Limitations section and
`reports/FINAL_REPORT.md` §6 for the full, honest account of what this
project does and does not support claiming.

## Contact

**Naman Khatak**
Indian Institute of Technology Mandi
namankhatak@gmail.com
