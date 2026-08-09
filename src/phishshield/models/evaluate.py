"""Evaluation harness: precision/recall/F1/false-positive-rate per partition.

FPR is reported alongside the usual classification metrics because, per the
project brief, a phishing tool users are meant to trust lives or dies on how
often it cries wolf on legitimate sites — accuracy alone hides that.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from phishshield.models.classifier import predict_scores


def evaluate(model: HistGradientBoostingClassifier, df: pd.DataFrame, threshold: float = 0.5) -> dict:
    """Compute classification metrics for `model` on `df`.

    Returns a dict with `n_samples`, `precision`, `recall`, `f1`, `fpr`.
    Raises ValueError if `df` is empty. Single-class partitions are valid
    input (the LLM-generated holdout is phishing-only by construction —
    see Phase 2) and simply leave whichever metric is structurally
    undefined for that class mix as NaN (e.g. FPR has no meaning without
    any true negatives).
    """
    if df.empty:
        raise ValueError("df must be non-empty")

    scores = predict_scores(model, df)
    preds = (scores >= threshold).astype(int)
    y_true = df["label"]

    tn, fp, fn, tp = confusion_matrix(y_true, preds, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else float("nan")

    return {
        "n_samples": len(df),
        "precision": precision_score(y_true, preds, zero_division=0),
        "recall": recall_score(y_true, preds, zero_division=0),
        "f1": f1_score(y_true, preds, zero_division=0),
        "fpr": fpr,
    }


def compare_partitions(
    model: HistGradientBoostingClassifier, partitions: dict, threshold: float = 0.5
) -> pd.DataFrame:
    """Evaluate `model` on each named partition and return a comparison table.

    `partitions` maps a label (e.g. "legacy_test", "llm_holdout") to a
    feature dataframe. Row order follows dict insertion order, so callers
    control legacy-vs-LLM display order.
    """
    rows = []
    for name, part_df in partitions.items():
        metrics = evaluate(model, part_df, threshold=threshold)
        rows.append({"partition": name, **metrics})
    return pd.DataFrame(rows)
