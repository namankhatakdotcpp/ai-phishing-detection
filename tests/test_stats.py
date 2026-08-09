import pytest

from phishshield.data.generation import generate_llm_phishing_dataset
from phishshield.data.schema import Sample, Source
from phishshield.data.stats import dataset_stats


def test_dataset_stats_counts_by_source_and_label():
    samples = [
        Sample(url="https://p1.example", label=1, source=Source.PHISHTANK),
        Sample(url="https://p2.example", label=1, source=Source.PHISHTANK),
        Sample(url="https://b1.example", label=0, source=Source.TRANCO),
    ]

    stats = dataset_stats(samples)

    assert set(stats.columns) == {"source", "label", "count"}
    row = stats[(stats["source"] == "phishtank") & (stats["label"] == 1)]
    assert row["count"].iloc[0] == 2
    row = stats[(stats["source"] == "tranco") & (stats["label"] == 0)]
    assert row["count"].iloc[0] == 1
    assert stats["count"].sum() == len(samples)


def test_dataset_stats_rejects_empty_input():
    with pytest.raises(ValueError):
        dataset_stats([])


def test_dataset_stats_on_llm_generated_dataset():
    samples = generate_llm_phishing_dataset()
    stats = dataset_stats(samples)
    assert len(stats) == 1  # single source, single label (phishing-only)
    assert stats.iloc[0]["source"] == "llm_generated"
    assert stats.iloc[0]["label"] == 1
    assert stats.iloc[0]["count"] == len(samples)
