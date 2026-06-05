"""
Type: Utility
Generate honest v3 scorecard metrics (ALGO_MODEL_METRICS) for the dashboard.

The production scorecard used single-random-split numbers (optimistic, and one row
could share a song with the test set). This recomputes every scorecard field from
out-of-fold group-CV predictions on v3:
  - AUC / AP as mean + 2.5–97.5% band across repeated StratifiedGroupKFold
  - one honest confusion matrix at threshold 0.5 on calibrated OOF probabilities,
    from which precision / recall / F1 / accuracy follow
  - lift@10%, baseline accuracy (majority class)

Output is a ready-to-paste ALGO_MODEL_METRICS dict; interpretation strings are filled
in by hand afterwards (the per-algorithm framing from forecast.md §5).

Uses: data_anon.csv, train.py, models/v3/calibration.json
Persists in: stdout + analysis/scorecard_metrics.md
Triggers: manual run `python3 machine_learning/analysis/06_scorecard_metrics.py`
Depends on: xgboost, scikit-learn
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold, cross_val_predict
from xgboost import XGBClassifier

_HERE = os.path.dirname(os.path.abspath(__file__))
_ML = os.path.dirname(_HERE)
sys.path.insert(0, _ML)

from train import FEATURE_COLUMNS, build_dataset  # noqa: E402

DATA_PATH = os.environ.get("ML_TRAIN_DATA", os.path.join(_ML, "01_data", "data_anon.csv"))
CALIB_PATH = os.path.join(_ML, "models", "v3", "calibration.json")
OUT_MD = os.path.join(_HERE, "scorecard_metrics.md")
RANDOM_STATE = 42
N_SPLITS, N_REPEATS = 5, 3


def _xgb() -> XGBClassifier:
    return XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05,
                         subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                         random_state=RANDOM_STATE)


def _auc_ap_band(X, y, groups) -> dict:
    aucs, aps = [], []
    for rep in range(N_REPEATS):
        sgk = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True,
                                   random_state=RANDOM_STATE + rep)
        for tr, te in sgk.split(X, y, groups):
            clf = _xgb().fit(X.iloc[tr], y.iloc[tr])
            p = clf.predict_proba(X.iloc[te])[:, 1]
            if y.iloc[te].nunique() > 1:
                aucs.append(roc_auc_score(y.iloc[te], p))
                aps.append(average_precision_score(y.iloc[te], p))
    q = lambda a, x: float(np.quantile(a, x))  # noqa: E731
    return {"auc": round(float(np.mean(aucs)), 3),
            "auc_ci": [round(q(aucs, 0.025), 3), round(q(aucs, 0.975), 3)],
            "pr_ap": round(float(np.mean(aps)), 3),
            "ap_ci": [round(q(aps, 0.025), 3), round(q(aps, 0.975), 3)]}


def _confusion_at_half(X, y, groups, platt: dict) -> dict:
    """One OOF confusion matrix at calibrated-prob threshold 0.5."""
    oof = cross_val_predict(_xgb(), X, y, cv=GroupKFold(5), groups=groups,
                            method="predict_proba")[:, 1]
    p_cal = 1.0 / (1.0 + np.exp(-(platt["coef"] * oof + platt["intercept"])))
    pred = (p_cal >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc = (tp + tn) / len(y)
    order = np.argsort(p_cal)[::-1][: max(1, int(0.1 * len(y)))]
    base = y.mean()
    lift = float(y.values[order].mean() / base) if base else float("nan")
    return {"confusion": {"TN": int(tn), "FP": int(fp), "FN": int(fn), "TP": int(tp)},
            "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3),
            "accuracy": round(acc, 3), "lift_top10": round(lift, 1),
            "baseline_accuracy": round(float(max(base, 1 - base)), 3)}


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    ds = build_dataset(df.copy())
    groups = df["NameID"].values
    X = ds[FEATURE_COLUMNS]
    platt = json.load(open(CALIB_PATH))
    blocks = {}
    for algo, key in (("DW", "dw"), ("RR", "rr"), ("RADIO", "radio")):
        y = ds[f"y_{key}"]
        m = {"model_version": "v3", "test_n": int(len(y)), "eval": "group-CV (OOF)"}
        m.update(_auc_ap_band(X, y, groups))
        m.update(_confusion_at_half(X, y, groups, platt[key]))
        blocks[algo] = m
    lines = ["# v3 scorecard metrics (group-CV OOF)\n",
             "```python", json.dumps(blocks, indent=2), "```"]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    print(json.dumps(blocks, indent=2))
    print(f"\n[written] {OUT_MD}")


if __name__ == "__main__":
    main()
