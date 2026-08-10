# Phase 7 qualitative examples

Run mode: **legacy: real (+ 85 Tranco samples with fetched benign HTML); llm_generated: real (loaded from data/generated/llm_phishing_v1.jsonl)**.

### Legacy phishing correctly caught (before model)

- URL: `https://php-web-server--mexicoeducation.replit.app/`
- classifier_score: 1.000
- risk_score: 0
- Judge reasons:
  - No significant phishing indicators detected in structural features.

### LLM-generated sample missed by baseline, caught after mitigation

- URL: `https://appple.com/account/claim-refund`
- before_score: 0.006
- after_score: 0.774
- risk_score: 70
- Judge reasons:
  - Login form submits credentials to a different domain than the one hosting the page.
  - Page title/branding references a company whose domain doesn't match the site's actual domain.
  - Page loads JavaScript from an external, unrelated domain.
  - Page contains hidden elements, sometimes used to conceal tracking or malicious content.
