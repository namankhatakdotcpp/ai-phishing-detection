"""Fetch real HTML for benign login/signin pages, to fix a diagnosed
training-data gap: `num_password_fields` on legitimate login pages is a
high-impact false-positive driver (see reports/FINAL_REPORT.md Section 3.7
and the n=130 hard-negative re-run ablation that reconfirmed it -- 7/15
false positives driven primarily by this feature).

IMPORTANT -- domain-disjoint from the hard-negative EVALUATION set
(data/evaluation/hard_negatives_manifest.jsonl): every domain already used
there (Google, GitHub, Microsoft, ... see hard_negatives_fetch_log.txt) is
deliberately excluded here so the evaluation set stays an honest,
independent measure of generalization -- these are different, real,
legitimate SaaS/service login pages.

Only pages whose fetched HTML contains a real server-rendered
`type="password"` input are kept (many modern login pages are pure
client-rendered SPAs where curl's HTML has no such element -- those are
useless as training examples and are excluded, not faked).

Usage:
    python scripts/fetch_benign_login_pages.py
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_JSONL = REPO_ROOT / "data" / "generated" / "benign_login_pages.jsonl"
FETCH_LOG = REPO_ROOT / "data" / "evaluation" / "benign_login_fetch_log.txt"
UA = "PhishShield-AI/1.0 research (course project; benign login-page training sample)"
TIMEOUT = 8.0
MAX_HTML_BYTES = 300_000

# Deliberately NOT overlapping any domain in data/evaluation/hard_negatives_fetch_log.txt
URLS = [
    ("mailchimp_login", "https://login.mailchimp.com/"),
    ("hubspot_login", "https://app.hubspot.com/login"),
    ("zendesk_login", "https://www.zendesk.com/login/"),
    ("okta_login", "https://www.okta.com/login/"),
    ("intercom_login", "https://app.intercom.com/"),
    ("monday_login", "https://auth.monday.com/login"),
    ("clickup_login", "https://app.clickup.com/login"),
    ("basecamp_login", "https://basecamp.com/login"),
    ("evernote_login", "https://www.evernote.com/Login.action"),
    ("todoist_login", "https://todoist.com/auth/login"),
    ("grammarly_login", "https://www.grammarly.com/signin"),
    ("duolingo_login", "https://www.duolingo.com/"),
    ("udemy_login", "https://www.udemy.com/join/login-popup/"),
    ("patreon_login", "https://www.patreon.com/login"),
    ("kickstarter_login", "https://www.kickstarter.com/login"),
    ("eventbrite_login", "https://www.eventbrite.com/signin/"),
    ("yelp_login", "https://www.yelp.com/login"),
    ("ziprecruiter_login", "https://www.ziprecruiter.com/login"),
    ("zillow_login", "https://www.zillow.com/user/acct/login/"),
    ("chegg_login", "https://www.chegg.com/login"),
    ("quizlet_login", "https://quizlet.com/login"),
    ("sourceforge_login", "https://sourceforge.net/auth/"),
    ("sendgrid_login", "https://login.sendgrid.com/login"),
    ("twilio_login", "https://login.twilio.com/"),
    ("wise_login", "https://wise.com/login"),
    ("discord_login", "https://discord.com/login"),
    ("upwork_login", "https://www.upwork.com/ab/account-security/login"),
    ("fiverr_login", "https://www.fiverr.com/login"),
    ("freelancer_login", "https://www.freelancer.com/login"),
    ("envato_login", "https://account.envato.com/sign_in"),
    ("themeforest_login", "https://themeforest.net/sign_in"),
    ("bitwarden_login", "https://vault.bitwarden.com/#/login"),
    ("lastpass_login", "https://lastpass.com/"),
    ("namecheap_login", "https://www.namecheap.com/myaccount/login/"),
    ("godaddy_login", "https://sso.godaddy.com/"),
    ("hostgator_login", "https://portal.hostgator.com/login"),
    ("bluehost_login", "https://my.bluehost.com/hosting/login"),
    ("mailgun_login", "https://login.mailgun.com/login/"),
    ("surveymonkey_login", "https://www.surveymonkey.com/user/sign-in/"),
    ("typeform_login", "https://admin.typeform.com/login"),
    ("canva_alt_login", "https://www.canva.cn/login"),
]

PASSWORD_INPUT_RE = re.compile(r'type\s*=\s*["\']password["\']', re.IGNORECASE)


def fetch_one(name: str, url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            body = resp.read(MAX_HTML_BYTES)
    except Exception as exc:
        return name, url, None, str(exc)[:80]
    return name, url, status, body


def main() -> None:
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    FETCH_LOG.parent.mkdir(parents=True, exist_ok=True)

    results = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(fetch_one, name, url): (name, url) for name, url in URLS}
        for i, fut in enumerate(as_completed(futures), 1):
            name, url, status, payload = fut.result()
            if status == 200 and isinstance(payload, (bytes, bytearray)):
                html = payload.decode("utf-8", errors="replace")
                has_pw = bool(PASSWORD_INPUT_RE.search(html))
                results.append((name, url, len(payload), "ok" if has_pw else "no_password_field", html if has_pw else None))
            else:
                note = payload if isinstance(payload, str) else f"status={status}"
                results.append((name, url, 0, note, None))
            note = results[-1][3]
            print(f"[{i}/{len(URLS)}] {name}: {results[-1][2]} bytes, {note}")

    kept = [r for r in results if r[3] == "ok"]
    with open(FETCH_LOG, "w") as f:
        for name, url, size, note, _html in results:
            f.write(f"{name}|{url}|{size}|{note}\n")

    import json

    with open(OUT_JSONL, "w") as f:
        for name, url, size, note, html in kept:
            f.write(json.dumps({"url": url, "label": 0, "source": "tranco", "html": html}) + "\n")

    print(f"\n{len(kept)}/{len(URLS)} usable (real password field present). Wrote {OUT_JSONL}")


if __name__ == "__main__":
    main()
