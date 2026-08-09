"""Dataset partitioning.

Enforces the Phase 2 acceptance criterion structurally: `DatasetPartitions`
has no field that mixes `llm_holdout` into `train`/`legacy_test`, and
`build_partitions` is the only place that is allowed to move LLM-generated
samples out of the holdout partition (Phase 4's mitigation experiment does
that explicitly and separately — see `fold_in_llm_samples`).
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.model_selection import train_test_split

from phishshield.data.schema import Sample, Source


@dataclass(frozen=True)
class DatasetPartitions:
    train: list[Sample]
    legacy_test: list[Sample]
    llm_holdout: list[Sample]


def build_partitions(
    legacy_samples: list[Sample],
    llm_samples: list[Sample],
    test_size: float = 0.2,
    seed: int = 42,
) -> DatasetPartitions:
    """Split legacy samples into train/test; LLM-generated samples are never
    touched here and go entirely into `llm_holdout`.

    Raises ValueError if `llm_samples` contains anything other than
    `Source.LLM_GENERATED` — this partitioning is only meaningful when the
    two pools are cleanly separated by source.
    """
    if any(s.source != Source.LLM_GENERATED for s in llm_samples):
        raise ValueError("llm_samples must contain only Source.LLM_GENERATED samples")

    labels = [s.label for s in legacy_samples]
    train, legacy_test = train_test_split(
        legacy_samples,
        test_size=test_size,
        random_state=seed,
        stratify=labels,
    )

    return DatasetPartitions(train=train, legacy_test=legacy_test, llm_holdout=llm_samples)


def fold_in_llm_samples(
    partitions: DatasetPartitions, fraction: float, seed: int = 42
) -> DatasetPartitions:
    """Move a fraction of `llm_holdout` into `train`, for the Phase 4
    mitigation experiment. The remainder stays in `llm_holdout` so the eval
    harness always has an untouched LLM-generated test set.
    """
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between 0 and 1")

    if fraction == 0.0 or not partitions.llm_holdout:
        return partitions

    if fraction == 1.0:
        folded_in, remaining = partitions.llm_holdout, []
    else:
        folded_in, remaining = train_test_split(
            partitions.llm_holdout,
            train_size=fraction,
            random_state=seed,
        )

    return DatasetPartitions(
        train=partitions.train + folded_in,
        legacy_test=partitions.legacy_test,
        llm_holdout=remaining,
    )
