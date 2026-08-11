"""Task 4: strict old (v3) vs new (v4) evaluation on identical frozen
datasets, per FINAL_REPORT.md Section 3.11-3.13's requested methodology.

Loads both classifier artifacts directly (never retrains, never touches
either file), fuses each with the same, unmodified judge at the same
alpha=0.7 used everywhere else in this project, and reports metrics
per dataset. This script does not decide PASS/FAIL -- it only produces
the numbers Task 8's decision is made from.

Datasets evaluated:
  A. 130-page hard-negative set (static-fetch features, unmodified)
  B. Held-out browser-rendered benign set (31 pages, NEVER in training)
  C. LLM phishing holdout (144 samples)
  D. Legacy phishing test partition (real PhishTank/OpenPhish, held out)
  E. The specific live-captured problem pages from Section 3.12/3.13

Usage:
    python scripts/eval_v3_vs_v4.py
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import joblib
import pandas as pd
from bs4 import XMLParsedAsHTMLWarning
from sklearn.metrics import f1_score, precision_score, recall_score

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from phishshield.data.loaders import load_llm_generated, load_openphish, load_phishtank, load_tranco  # noqa: E402
from phishshield.data.pipeline import build_feature_dataframe  # noqa: E402
from phishshield.judge.judge import judge_dataframe, risk_band  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
V3_PATH = REPO_ROOT / "artifacts" / "phishing_classifier_v3_current_frozen_70e68ee0.joblib"
V4_PATH = REPO_ROOT / "artifacts" / "phishing_classifier_v4_candidate.joblib"
ALPHA = 0.7

PROBLEM_PAGES = [
    "wellsfargo", "bankofamerica", "google_accounts", "instagram", "reddit_home", "youtube_watch",
]


def load_models():
    v3 = joblib.load(V3_PATH)
    v4 = joblib.load(V4_PATH)
    return v3, v4


def score_dataframe(df: pd.DataFrame, model, feature_cols: list[str]) -> pd.DataFrame:
    X = df[feature_cols]
    classifier_scores = model.predict_proba(X)[:, 1]
    judge_scores = judge_dataframe(df)
    fused = ALPHA * classifier_scores + (1 - ALPHA) * judge_scores
    risk = (fused * 100).round().astype(int)
    bands = risk.apply(risk_band)
    out = df.copy()
    out["classifier_score"] = classifier_scores
    out["judge_score"] = judge_scores
    out["risk_score"] = risk
    out["risk_band"] = bands
    return out


def eval_labeled(name: str, df: pd.DataFrame, model, feature_cols: list[str]) -> dict:
    scored = score_dataframe(df, model, feature_cols)
    y_true = df["label"].values
    y_pred = (scored["risk_score"] >= 50).astype(int).values
    n = len(df)
    fpr = None
    if (y_true == 0).sum() > 0:
        fpr = ((y_pred == 1) & (y_true == 0)).sum() / (y_true == 0).sum()
    metrics = {
        "n": n,
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "fpr": round(float(fpr), 4) if fpr is not None else None,
        "n_high": int((scored["risk_band"] == "high").sum()),
        "n_medium": int((scored["risk_band"] == "medium").sum()),
        "n_low": int((scored["risk_band"] == "low").sum()),
    }
    return metrics


def main():
    v3, v4 = load_models()
    feature_cols_v3 = list(v3.feature_names_in_)
    feature_cols_v4 = list(v4.feature_names_in_)
    assert feature_cols_v3 == feature_cols_v4, "feature schema mismatch between v3 and v4 -- must be identical"
    feature_cols = feature_cols_v3

    results = {}

    # --- A. 130-page hard-negative set (static features, from manifest) ---
    rows = []
    with open(REPO_ROOT / "data" / "evaluation" / "hard_negatives_manifest.jsonl") as f:
        for line in f:
            row = json.loads(line)
            if row.get("status") != "included":
                continue
            feats = dict(row["features"])
            feats.pop("_meta_url", None)
            feats.pop("_meta_title", None)
            feats["label"] = 0
            feats["name"] = row["name"]
            rows.append(feats)
    hn_df = pd.DataFrame(rows)
    for label, model in (("v3", v3), ("v4", v4)):
        scored = score_dataframe(hn_df, model, feature_cols)
        results.setdefault("A_hard_negatives_130", {})[label] = {
            "n": len(hn_df),
            "fpr_ge50": round(float((scored["risk_score"] >= 50).mean()), 4),
            "n_high": int((scored["risk_band"] == "high").sum()),
            "n_medium": int((scored["risk_band"] == "medium").sum()),
            "n_low": int((scored["risk_band"] == "low").sum()),
            "median": int(scored["risk_score"].median()),
            "p90": int(scored["risk_score"].quantile(0.9)),
            "max": int(scored["risk_score"].max()),
        }

    # --- B. Held-out browser-rendered benign set (31 pages, never trained on) ---
    heldout_samples = load_llm_generated(REPO_ROOT / "data" / "generated" / "benign_browser_rendered_heldout.jsonl")
    heldout_df = build_feature_dataframe(heldout_samples)
    for label, model in (("v3", v3), ("v4", v4)):
        scored = score_dataframe(heldout_df, model, feature_cols)
        results.setdefault("B_browser_heldout_31", {})[label] = {
            "n": len(heldout_df),
            "fpr_ge50": round(float((scored["risk_score"] >= 50).mean()), 4),
            "n_high": int((scored["risk_band"] == "high").sum()),
            "n_medium": int((scored["risk_band"] == "medium").sum()),
            "n_low": int((scored["risk_band"] == "low").sum()),
            "median": int(scored["risk_score"].median()),
            "max": int(scored["risk_score"].max()),
        }

    # --- C. LLM phishing holdout (144 samples) ---
    llm_samples = load_llm_generated(REPO_ROOT / "data" / "generated" / "llm_phishing_v1.jsonl")
    llm_df = build_feature_dataframe(llm_samples)
    for label, model in (("v3", v3), ("v4", v4)):
        results.setdefault("C_llm_phishing_144", {})[label] = eval_labeled("C", llm_df, model, feature_cols)

    # --- D. Legacy phishing test (real PhishTank + OpenPhish, sampled for speed) ---
    phishtank = load_phishtank(REPO_ROOT / "data" / "raw" / "phishtank.csv")
    openphish = load_openphish(REPO_ROOT / "data" / "raw" / "openphish.txt")
    tranco = load_tranco(REPO_ROOT / "data" / "raw" / "tranco.csv", limit=3000)
    import random

    rng = random.Random(42)
    legacy_phish_sample = rng.sample(phishtank, min(3000, len(phishtank))) + openphish
    legacy_samples = legacy_phish_sample + tranco
    legacy_df = build_feature_dataframe(legacy_samples)
    for label, model in (("v3", v3), ("v4", v4)):
        results.setdefault("D_legacy_test_sampled", {})[label] = eval_labeled("D", legacy_df, model, feature_cols)

    # --- E. Specific live-captured problem pages ---
    live = {}
    with open(REPO_ROOT / "data" / "evaluation" / "browser_rendered_features.jsonl") as f:
        for line in f:
            row = json.loads(line)
            if row.get("status") == "ok":
                live[row["name"]] = row["features"]
    prob_rows = []
    for name in PROBLEM_PAGES:
        if name not in live:
            continue
        feats = dict(live[name])
        feats.pop("_meta_url", None)
        feats.pop("_meta_title", None)
        feats["name"] = name
        prob_rows.append(feats)
    prob_df = pd.DataFrame(prob_rows)
    prob_out = {}
    for label, model in (("v3", v3), ("v4", v4)):
        scored = score_dataframe(prob_df.drop(columns=["name"]), model, feature_cols)
        for i, name in enumerate(prob_df["name"]):
            prob_out.setdefault(name, {})[label] = {
                "risk_score": int(scored.iloc[i]["risk_score"]),
                "risk_band": scored.iloc[i]["risk_band"],
                "classifier_score": round(float(scored.iloc[i]["classifier_score"]), 4),
                "judge_score": round(float(scored.iloc[i]["judge_score"]), 4),
            }
    results["E_live_problem_pages"] = prob_out

    print(json.dumps(results, indent=2))
    with open(REPO_ROOT / "data" / "evaluation" / "v3_vs_v4_eval.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
