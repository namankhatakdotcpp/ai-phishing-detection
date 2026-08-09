"""Phase 4 mitigation experiment.

Two questions, one experiment:

1. Before/after: does folding a fraction of the LLM-generated partition
   into training close the legacy->LLM detection gap measured in Phase 3?
2. Ablation: on top of the mitigated model, does fusing in the (mocked)
   judge score help further?

Both models are evaluated on the *same* held-out sets — `legacy_test` is
untouched by folding, and the LLM-generated remainder (the samples not
folded into training) is the only fair LLM-generated test set once the
"after" model has trained on part of that pool.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from phishshield.data.pipeline import build_feature_dataframe
from phishshield.data.schema import Sample
from phishshield.data.splits import build_partitions, fold_in_llm_samples
from phishshield.judge.judge import judge_dataframe
from phishshield.models.classifier import predict_scores, train_classifier
from phishshield.models.evaluate import evaluate, evaluate_scores
from phishshield.models.fusion import fuse_scores


@dataclass(frozen=True)
class MitigationResult:
    before_after: pd.DataFrame
    ablation: pd.DataFrame
    before_model: HistGradientBoostingClassifier
    after_model: HistGradientBoostingClassifier


def run_mitigation_experiment(
    legacy_samples: list[Sample],
    llm_samples: list[Sample],
    fold_fraction: float = 0.5,
    test_size: float = 0.2,
    seed: int = 42,
    alpha: float = 0.5,
    threshold: float = 0.5,
) -> MitigationResult:
    """Run the before/after retraining comparison and the classifier-only
    vs. classifier+judge ablation, and return both as tables.

    `alpha` is the classifier's weight in the fusion ablation (see
    `phishshield.models.fusion.fuse_scores`).
    """
    partitions = build_partitions(legacy_samples, llm_samples, test_size=test_size, seed=seed)
    folded = fold_in_llm_samples(partitions, fraction=fold_fraction, seed=seed)

    before_model = train_classifier(build_feature_dataframe(partitions.train))
    after_model = train_classifier(build_feature_dataframe(folded.train))

    legacy_test_df = build_feature_dataframe(partitions.legacy_test)
    llm_remainder_df = (
        build_feature_dataframe(folded.llm_holdout) if folded.llm_holdout else None
    )

    eval_partitions = {"legacy_test": legacy_test_df}
    if llm_remainder_df is not None:
        eval_partitions["llm_holdout_remainder"] = llm_remainder_df

    before_after_rows = []
    for model_name, model in (("before", before_model), ("after", after_model)):
        for partition_name, part_df in eval_partitions.items():
            metrics = evaluate(model, part_df, threshold=threshold)
            before_after_rows.append({"model": model_name, "partition": partition_name, **metrics})
    before_after = pd.DataFrame(before_after_rows)

    ablation_rows = []
    for partition_name, part_df in eval_partitions.items():
        classifier_scores = predict_scores(after_model, part_df)
        classifier_metrics = evaluate_scores(part_df["label"], classifier_scores, threshold=threshold)
        ablation_rows.append(
            {"variant": "classifier_only", "partition": partition_name, **classifier_metrics}
        )

        judge_scores = judge_dataframe(part_df)
        fused_scores = fuse_scores(classifier_scores, judge_scores, alpha=alpha)
        fused_metrics = evaluate_scores(part_df["label"], fused_scores, threshold=threshold)
        ablation_rows.append(
            {"variant": "classifier_plus_judge", "partition": partition_name, **fused_metrics}
        )
    ablation = pd.DataFrame(ablation_rows)

    return MitigationResult(
        before_after=before_after,
        ablation=ablation,
        before_model=before_model,
        after_model=after_model,
    )
