# Phase 7 qualitative examples

Run mode: **legacy: synthetic (illustrative only); llm_generated: real (loaded from data/generated/llm_phishing_v1.jsonl)**.

### Legacy phishing correctly caught (before model)

- URL: `https://cloudpay-secure-38.verify-login.xyz/signin`
- classifier_score: 1.000
- risk_score: 60
- Judge reasons:
  - Login form submits credentials to a different domain than the one hosting the page.
  - Domain uses a top-level domain commonly abused for throwaway phishing registrations.
  - Page loads JavaScript from an external, unrelated domain.
  - Page contains hidden elements, sometimes used to conceal tracking or malicious content.

### LLM-generated sample missed by baseline, caught after mitigation

- URL: `https://chaase.com/account/verify-now`
- before_score: 0.000
- after_score: 1.000
- risk_score: 70
- Judge reasons:
  - Login form submits credentials to a different domain than the one hosting the page.
  - Page title/branding references a company whose domain doesn't match the site's actual domain.
  - Page loads JavaScript from an external, unrelated domain.
  - Page contains hidden elements, sometimes used to conceal tracking or malicious content.
