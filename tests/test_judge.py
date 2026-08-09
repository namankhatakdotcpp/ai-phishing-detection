import json
from pathlib import Path

from phishshield.data.pipeline import build_feature_dataframe
from phishshield.data.schema import Sample, Source
from phishshield.features.pipeline import extract_features
from phishshield.judge.judge import _RULES, judge_dataframe, judge_features, save_judge_log

FIXTURES = Path(__file__).parent / "fixtures"


def test_clean_features_score_low_with_default_reason():
    verdict = judge_features({})
    assert verdict.risk_score == 0
    assert verdict.risk_band == "low"
    assert verdict.reasons == [
        "No significant phishing indicators detected in structural features."
    ]


def test_risk_score_is_capped_at_100():
    heavily_flagged = {
        "num_password_fields": 1,
        "has_external_form_action": 1,
        "title_brand_mismatch": 1,
        "has_ip_literal": 1,
        "has_suspicious_tld": 1,
        "has_at_symbol": 1,
        "is_https": 0,
        "num_subdomains": 3,
        "num_external_js_domains": 2,
        "num_hidden_elements": 2,
        "special_char_ratio": 0.5,
    }
    verdict = judge_features(heavily_flagged)
    assert verdict.risk_score == 100
    assert verdict.risk_band == "high"
    assert len(verdict.reasons) == len(_RULES)  # every rule tripped


def test_risk_band_thresholds():
    assert judge_features({"has_at_symbol": 1}).risk_band == "low"  # weight 15 < 40
    assert (
        judge_features({"has_at_symbol": 1, "has_suspicious_tld": 1, "is_https": 0}).risk_band
        == "medium"
    )  # 15+15+10 = 40
    high = judge_features(
        {
            "num_password_fields": 1,
            "has_external_form_action": 1,
            "title_brand_mismatch": 1,
            "has_ip_literal": 1,
        }
    )
    assert high.risk_score == 75  # 30+25+20 = 75 >= 70
    assert high.risk_band == "high"


def test_phishing_fixture_scores_higher_than_benign_fixture():
    phishing_html = (FIXTURES / "phishing_paypal_clone.html").read_text()
    benign_html = (FIXTURES / "benign_example.html").read_text()

    phishing_sample = Sample(
        url="https://paypal-secure-login.verify-account.xyz/login",
        label=1,
        source=Source.PHISHTANK,
        html=phishing_html,
    )
    benign_sample = Sample(
        url="https://example.com/",
        label=0,
        source=Source.TRANCO,
        html=benign_html,
    )

    phishing_verdict = judge_features(extract_features(phishing_sample))
    benign_verdict = judge_features(extract_features(benign_sample))

    assert phishing_verdict.risk_score > benign_verdict.risk_score
    assert phishing_verdict.risk_band in ("medium", "high")
    assert benign_verdict.risk_band == "low"


def test_judge_dataframe_returns_aligned_0_to_1_scores():
    phishing_html = (FIXTURES / "phishing_paypal_clone.html").read_text()
    benign_html = (FIXTURES / "benign_example.html").read_text()
    samples = [
        Sample(
            url="https://paypal-secure-login.verify-account.xyz/login",
            label=1,
            source=Source.PHISHTANK,
            html=phishing_html,
        ),
        Sample(url="https://example.com/", label=0, source=Source.TRANCO, html=benign_html),
    ]
    df = build_feature_dataframe(samples)

    scores = judge_dataframe(df)

    assert scores.name == "judge_score"
    assert list(scores.index) == list(df.index)
    assert scores.between(0, 1).all()
    assert scores.iloc[0] > scores.iloc[1]  # phishing row scores higher than benign row


def _two_row_df():
    phishing_html = (FIXTURES / "phishing_paypal_clone.html").read_text()
    benign_html = (FIXTURES / "benign_example.html").read_text()
    samples = [
        Sample(
            url="https://paypal-secure-login.verify-account.xyz/login",
            label=1,
            source=Source.PHISHTANK,
            html=phishing_html,
        ),
        Sample(url="https://example.com/", label=0, source=Source.TRANCO, html=benign_html),
    ]
    return build_feature_dataframe(samples)


def test_judge_dataframe_log_is_none_by_default_and_optional():
    df = _two_row_df()
    scores = judge_dataframe(df)  # no `log` kwarg -> must not raise
    assert len(scores) == 2


def test_judge_dataframe_logs_one_record_per_row():
    df = _two_row_df()
    log: list = []

    scores = judge_dataframe(df, log=log)

    assert len(log) == len(df)
    for (idx, row), record in zip(df.iterrows(), log):
        assert record["index"] == idx
        assert isinstance(record["features"], dict)
        assert record["risk_score"] == round(scores.loc[idx] * 100)
        assert record["risk_band"] in ("low", "medium", "high")
        assert isinstance(record["reasons"], list) and record["reasons"]


def test_save_judge_log_round_trips_as_jsonl(tmp_path):
    df = _two_row_df()
    log: list = []
    judge_dataframe(df, log=log)
    out_path = tmp_path / "judge_log.jsonl"

    save_judge_log(log, out_path)

    lines = out_path.read_text().strip().splitlines()
    assert len(lines) == len(log)
    for line, expected in zip(lines, log):
        assert json.loads(line) == expected
