import argparse

import pytest

from phishshield.models.build_report_assets import _format_example_md, _load_legacy_samples, run


def _default_args(**overrides):
    defaults = dict(
        phishtank=None,
        openphish=None,
        tranco=None,
        tranco_limit=5000,
        tranco_html=None,
        extra_benign_html=[],
        llm_generated=None,
        synthetic_n=10,
        fold_fraction=0.5,
        test_size=0.25,
        alpha=0.5,
        seed=1,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_load_legacy_samples_defaults_to_synthetic():
    samples, mode = _load_legacy_samples(_default_args())
    assert mode.startswith("synthetic")
    assert len(samples) == 20  # synthetic_n=10 per class


def test_load_legacy_samples_requires_all_three_real_data_flags_together():
    args = _default_args(phishtank="x.csv")  # openphish/tranco missing
    with pytest.raises(SystemExit):
        _load_legacy_samples(args)


def test_load_legacy_samples_merges_tranco_html_by_url(tmp_path):
    from phishshield.data.generation import save_samples_jsonl
    from phishshield.data.schema import Sample, Source

    phishtank_csv = tmp_path / "phishtank.csv"
    phishtank_csv.write_text("url\nhttps://evil.example/login\n")
    openphish_txt = tmp_path / "openphish.txt"
    openphish_txt.write_text("https://evil2.example/login\n")
    tranco_csv = tmp_path / "tranco.csv"
    tranco_csv.write_text("1,good.example\n2,other.example\n")
    tranco_html_path = tmp_path / "tranco_html.jsonl"
    save_samples_jsonl(
        [Sample(url="https://good.example", label=0, source=Source.TRANCO, html="<html>real</html>")],
        tranco_html_path,
    )

    args = _default_args(
        phishtank=str(phishtank_csv),
        openphish=str(openphish_txt),
        tranco=str(tranco_csv),
        tranco_html=str(tranco_html_path),
    )
    samples, mode = _load_legacy_samples(args)

    assert "+ 1 Tranco samples with fetched benign HTML" in mode
    assert len(samples) == 4  # 1 phishtank + 1 openphish + 2 tranco (1 enriched, 1 plain)
    good = next(s for s in samples if s.url == "https://good.example")
    assert good.html == "<html>real</html>"


def test_format_example_md_handles_none():
    md = _format_example_md("Some Title", None, ["classifier_score"])
    assert "Some Title" in md
    assert "No matching example found" in md


def test_format_example_md_renders_example_fields():
    example = {
        "url": "https://evil.example/login",
        "classifier_score": 0.987,
        "risk_score": 85,
        "reasons": ["reason one", "reason two"],
    }
    md = _format_example_md("Caught", example, ["classifier_score", "risk_score"])
    assert "https://evil.example/login" in md
    assert "0.987" in md
    assert "85" in md
    assert "reason one" in md and "reason two" in md


def test_run_writes_all_expected_report_assets(tmp_path):
    args = _default_args(synthetic_n=25, test_size=0.3, fold_fraction=0.5)
    output_dir = tmp_path / "reports"

    run(args, output_dir)

    expected_files = [
        "phase7_dataset_stats.csv",
        "phase7_judge_log.jsonl",
        "phase7_phase3_eval.csv",
        "phase7_phase3_eval.png",
        "phase7_phase4_before_after.csv",
        "phase7_phase4_before_after_recall.png",
        "phase7_phase4_ablation.csv",
        "phase7_phase4_ablation_recall.png",
        "phase7_qualitative_examples.md",
    ]
    for filename in expected_files:
        path = output_dir / filename
        assert path.exists(), filename
        assert path.stat().st_size > 0, filename

    qualitative_md = (output_dir / "phase7_qualitative_examples.md").read_text()
    assert "Run mode: **legacy: synthetic" in qualitative_md
    assert "llm_generated: mocked" in qualitative_md


def test_run_labels_real_llm_generated_partition_distinctly(tmp_path):
    real_llm_path = tmp_path / "real_llm.jsonl"
    from phishshield.data.generation import generate_llm_phishing_dataset
    from phishshield.data.generation import save_samples_jsonl

    save_samples_jsonl(generate_llm_phishing_dataset(), real_llm_path)

    args = _default_args(synthetic_n=25, llm_generated=str(real_llm_path))
    output_dir = tmp_path / "reports"

    run(args, output_dir)

    qualitative_md = (output_dir / "phase7_qualitative_examples.md").read_text()
    assert "llm_generated: real (loaded from" in qualitative_md
    assert "legacy: synthetic" in qualitative_md
