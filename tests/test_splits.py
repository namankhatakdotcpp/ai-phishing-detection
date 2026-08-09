import pytest

from phishshield.data.generation import generate_llm_phishing_dataset
from phishshield.data.schema import Sample, Source
from phishshield.data.splits import build_partitions, fold_in_llm_samples


def _legacy_samples(n_phish=20, n_benign=20):
    samples = [
        Sample(url=f"https://phish{i}.example/login", label=1, source=Source.PHISHTANK)
        for i in range(n_phish)
    ]
    samples += [
        Sample(url=f"https://benign{i}.example", label=0, source=Source.TRANCO)
        for i in range(n_benign)
    ]
    return samples


def test_llm_samples_never_appear_in_train_or_legacy_test():
    legacy = _legacy_samples()
    llm = generate_llm_phishing_dataset()

    partitions = build_partitions(legacy, llm, test_size=0.25, seed=1)

    train_sources = {s.source for s in partitions.train}
    test_sources = {s.source for s in partitions.legacy_test}
    assert Source.LLM_GENERATED not in train_sources
    assert Source.LLM_GENERATED not in test_sources
    assert set(partitions.llm_holdout) == set(llm)


def test_train_and_legacy_test_partition_all_legacy_samples():
    legacy = _legacy_samples()
    llm = generate_llm_phishing_dataset()
    partitions = build_partitions(legacy, llm, test_size=0.25, seed=1)

    assert len(partitions.train) + len(partitions.legacy_test) == len(legacy)
    assert set(partitions.train) | set(partitions.legacy_test) == set(legacy)
    assert set(partitions.train).isdisjoint(partitions.legacy_test)


def test_build_partitions_rejects_non_llm_samples_in_llm_pool():
    legacy = _legacy_samples()
    bad_llm_pool = _legacy_samples(n_phish=1, n_benign=0)  # wrong source
    with pytest.raises(ValueError):
        build_partitions(legacy, bad_llm_pool)


def test_fold_in_llm_samples_moves_fraction_into_train():
    legacy = _legacy_samples()
    llm = generate_llm_phishing_dataset()
    partitions = build_partitions(legacy, llm, test_size=0.25, seed=1)

    folded = fold_in_llm_samples(partitions, fraction=0.5, seed=1)

    assert len(folded.llm_holdout) < len(partitions.llm_holdout)
    assert len(folded.train) > len(partitions.train)
    assert len(folded.train) + len(folded.llm_holdout) == len(partitions.train) + len(
        partitions.llm_holdout
    )
    # legacy_test must never be touched by folding in LLM samples
    assert folded.legacy_test == partitions.legacy_test


def test_fold_in_llm_samples_zero_fraction_is_noop():
    legacy = _legacy_samples()
    llm = generate_llm_phishing_dataset()
    partitions = build_partitions(legacy, llm, test_size=0.25, seed=1)

    folded = fold_in_llm_samples(partitions, fraction=0.0)

    assert folded.train == partitions.train
    assert folded.llm_holdout == partitions.llm_holdout


def test_fold_in_llm_samples_rejects_out_of_range_fraction():
    legacy = _legacy_samples()
    llm = generate_llm_phishing_dataset()
    partitions = build_partitions(legacy, llm, test_size=0.25, seed=1)
    with pytest.raises(ValueError):
        fold_in_llm_samples(partitions, fraction=1.5)
