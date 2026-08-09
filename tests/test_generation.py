from urllib.parse import urlsplit

from phishshield.data.generation import (
    BRANDS,
    OBFUSCATIONS,
    TONES,
    generate_llm_phishing_dataset,
    save_samples_jsonl,
)
from phishshield.data.loaders import load_llm_generated
from phishshield.data.pipeline import build_feature_dataframe
from phishshield.data.schema import Source


def test_generates_full_brand_tone_obfuscation_grid():
    samples = generate_llm_phishing_dataset()
    assert len(samples) == len(BRANDS) * len(TONES) * len(OBFUSCATIONS)


def test_all_generated_samples_are_labeled_phishing_from_llm_source():
    samples = generate_llm_phishing_dataset()
    assert all(s.label == 1 for s in samples)
    assert all(s.source == Source.LLM_GENERATED for s in samples)
    assert all(s.brand_target is not None for s in samples)
    assert all(s.html for s in samples)


def test_generation_is_deterministic_given_seed():
    a = generate_llm_phishing_dataset(seed=7)
    b = generate_llm_phishing_dataset(seed=7)
    assert [s.url for s in a] == [s.url for s in b]
    assert [s.html for s in a] == [s.html for s in b]


def test_different_seeds_can_still_change_exfil_host_choice():
    # Domains/paths are deterministic by design (brand/tone/technique), but
    # the exfil host is seed-dependent — confirms `seed` actually plumbs
    # through rather than being a decorative parameter.
    a = generate_llm_phishing_dataset(seed=1)
    b = generate_llm_phishing_dataset(seed=999)
    assert [s.html for s in a] != [s.html for s in b]


def test_obfuscated_domain_differs_from_real_brand_domain():
    real_domains = {key: domain for key, _, domain in BRANDS}
    samples = generate_llm_phishing_dataset()
    for sample in samples:
        hosted_domain = urlsplit(sample.url).hostname
        assert hosted_domain != real_domains[sample.brand_target]


def test_generated_samples_flow_through_phase1_pipeline():
    samples = generate_llm_phishing_dataset()[:5]
    df = build_feature_dataframe(samples)
    assert len(df) == 5
    # phishing-shaped templates should trip the password/form-action signals
    assert (df["num_password_fields"] >= 1).all()
    assert (df["has_external_form_action"] == 1).all()


def test_save_and_load_round_trip(tmp_path):
    samples = generate_llm_phishing_dataset()
    out_path = tmp_path / "llm_phishing.jsonl"
    save_samples_jsonl(samples, out_path)

    loaded = load_llm_generated(out_path)

    assert len(loaded) == len(samples)
    assert [s.url for s in loaded] == [s.url for s in samples]
    assert [s.html for s in loaded] == [s.html for s in samples]
    assert [s.brand_target for s in loaded] == [s.brand_target for s in samples]
    assert all(s.source == Source.LLM_GENERATED for s in loaded)
