# Phase 7 qualitative examples

Run mode: **legacy: real (+ 157 Tranco samples with fetched benign HTML); llm_generated: real (loaded from data/generated/llm_phishing_v1.jsonl)**.

### Legacy phishing correctly caught (before model)

- URL: `http://www.allegrolokalne.382839j56.shop`
- classifier_score: 1.000
- risk_score: 20
- Judge reasons:
  - Connection is not secured with HTTPS.
  - Unusually long subdomain chain, often used to disguise the real domain.

### LLM-generated sample missed by baseline, caught after mitigation

No matching example found in this run.
