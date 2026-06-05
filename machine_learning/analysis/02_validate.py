"""
Type: Utility
Rigorous validation harness for the 3 trigger classifiers — the methodological
core of the independent re-derivation.

It answers three questions the production single-split cannot:
  1. How inflated is the reported AUC once the same song can no longer sit in both
     train and test? (random split vs StratifiedGroupKFold on NameID)
  2. Which imbalance strategy actually helps, judged on BOTH ranking (AP/ROC-AUC)
     and calibration (Brier/ECE)? (none / scale_pos_weight / SMOTE)
  3. Which calibration method is honest when fit by cross-validation rather than on
     the test set? (raw / Platt-sigmoid / isotonic, all cross-fitted)

Every number is a mean over repeated group folds with a 2.5–97.5 percentile band,
never a single point estimate.

Uses: machine_learning/01_data/data_anon.csv, train.py (build_dataset, FEATURE_COLUMNS)
Persists in: machine_learning/analysis/validation.md
Triggers: manual run `python3 machine_learning/analysis/02_validate.py`
Depends on: xgboost, scikit-learn, imbalanced-learn
"""
import os
import sys

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold, train_test_split
from xgboost import XGBClassifier

_HERE = os.path.dirname(os.path.abspath(__file__))
_ML = os.path.dirname(_HERE)
sys.path.insert(0, _ML)

from train import FEATURE_COLUMNS, build_dataset  # noqa: E402

DATA_PATH = os.environ.get("ML_TRAIN_DATA", os.path.join(_ML, "01_data", "data_anon.csv"))
OUT_MD = os.path.join(_HERE, "validation.md")
RANDOM_STATE = 42
N_SPLITS, N_REPEATS = 5, 3


def _xgb(scale_pos_weight: float = 1.0) -> XGBClassifier:
    """Same hyperparameters as production train.py, optional imbalance weighting."""
    return XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05, subsample=0.9,
        colsample_bytree=0.9, eval_metric="logloss", random_state=RANDOM_STATE,
        scale_pos_weight=scale_pos_weight,
    )


def _ece(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error: |confidence − accuracy| averaged over prob bins."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            ece += (m.mean()) * abs(p[m].mean() - y[m].mean())
    return float(ece)


def _lift_at_k(y: np.ndarray, p: np.ndarray, k: float = 0.1) -> float:
    """Precision in the top-k fraction of scores, divided by base rate."""
    n = max(1, int(len(p) * k))
    top = np.argsort(p)[::-1][:n]
    base = y.mean()
    return float(y[top].mean() / base) if base > 0 else float("nan")


def _metrics(y: np.ndarray, p: np.ndarray) -> dict:
    if len(np.unique(y)) < 2:
        return {}
    return {"AP": average_precision_score(y, p), "ROC_AUC": roc_auc_score(y, p),
            "lift@10%": _lift_at_k(y, p), "Brier": brier_score_loss(y, p),
            "ECE": _ece(y, p)}


def _fit_predict(X, y, tr, te, imbalance: str, calib: str) -> np.ndarray:
    """Train one fold variant and return test probabilities (honest calibration)."""
    Xtr, ytr, Xte = X.iloc[tr], y.iloc[tr], X.iloc[te]
    spw = 1.0
    if imbalance == "scale_pos_weight":
        pos = max(1, int(ytr.sum()))
        spw = (len(ytr) - pos) / pos
    if imbalance == "smote" and ytr.sum() >= 6:
        Xtr, ytr = SMOTE(random_state=RANDOM_STATE).fit_resample(Xtr, ytr)
    base = _xgb(spw)
    if calib == "raw":
        return base.fit(Xtr, ytr).predict_proba(Xte)[:, 1]
    method = "sigmoid" if calib == "platt" else "isotonic"
    cc = CalibratedClassifierCV(base, method=method, cv=3)
    return cc.fit(Xtr, ytr).predict_proba(Xte)[:, 1]


def cv_evaluate(X, y, groups, imbalance: str, calib: str) -> dict:
    """Repeated StratifiedGroupKFold; return mean + 95% band per metric."""
    rows: list[dict] = []
    for rep in range(N_REPEATS):
        sgk = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True,
                                   random_state=RANDOM_STATE + rep)
        for tr, te in sgk.split(X, y, groups):
            p = _fit_predict(X, y, tr, te, imbalance, calib)
            m = _metrics(y.iloc[te].values, p)
            if m:
                rows.append(m)
    df = pd.DataFrame(rows)
    return {c: (df[c].mean(), df[c].quantile(0.025), df[c].quantile(0.975))
            for c in df.columns}


def _naive_auc(X, y) -> float:
    """Reproduce train.py's exact random 80/20 split AUC (the inflated number)."""
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2,
                                          random_state=RANDOM_STATE, stratify=y)
    if ytr.sum() >= 6:
        Xtr, ytr = SMOTE(random_state=RANDOM_STATE).fit_resample(Xtr, ytr)
    p = _xgb().fit(Xtr, ytr).predict_proba(Xte)[:, 1]
    return float(roc_auc_score(yte, p))


def _fmt(stat: tuple) -> str:
    m, lo, hi = stat
    return f"{m:.3f} [{lo:.3f}–{hi:.3f}]"


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    ds = build_dataset(df.copy())
    groups = df["NameID"].values
    X = ds[FEATURE_COLUMNS]
    lines = ["# Validation — honest group-CV vs the production single split\n",
             f"StratifiedGroupKFold(n_splits={N_SPLITS}) × {N_REPEATS} repeats, "
             f"grouped by `NameID`. Cells: mean [2.5%–97.5%].\n"]

    lines.append("## A. Random-split AUC vs group-CV ROC-AUC (leakage inflation)\n")
    lines.append("| algo | naive random-split AUC | honest group-CV ROC-AUC | inflation |")
    lines.append("|---|---|---|---|")
    honest: dict[str, dict] = {}
    for algo in ("dw", "rr", "radio"):
        y = ds[f"y_{algo}"]
        naive = _naive_auc(X, y)
        res = cv_evaluate(X, y, groups, "scale_pos_weight", "raw")
        honest[algo] = res
        gap = naive - res["ROC_AUC"][0]
        lines.append(f"| {algo} | {naive:.3f} | {_fmt(res['ROC_AUC'])} | "
                     f"**{gap:+.3f}** |")

    lines.append("\n## B. Imbalance strategy (group-CV, raw probabilities)\n")
    lines.append("| algo | strategy | AP | ROC-AUC | Brier | ECE |")
    lines.append("|---|---|---|---|---|---|")
    for algo in ("dw", "rr", "radio"):
        y = ds[f"y_{algo}"]
        for strat in ("none", "scale_pos_weight", "smote"):
            r = cv_evaluate(X, y, groups, strat, "raw")
            lines.append(f"| {algo} | {strat} | {_fmt(r['AP'])} | "
                         f"{_fmt(r['ROC_AUC'])} | {_fmt(r['Brier'])} | {_fmt(r['ECE'])} |")

    lines.append("\n## C. Calibration method (group-CV, imbalance=none, cross-fitted)\n")
    lines.append("| algo | calibration | Brier | ECE | AP |")
    lines.append("|---|---|---|---|---|")
    for algo in ("dw", "rr", "radio"):
        y = ds[f"y_{algo}"]
        for cal in ("raw", "platt", "isotonic"):
            r = cv_evaluate(X, y, groups, "none", cal)
            lines.append(f"| {algo} | {cal} | {_fmt(r['Brier'])} | "
                         f"{_fmt(r['ECE'])} | {_fmt(r['AP'])} |")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n[written] {OUT_MD}")


if __name__ == "__main__":
    main()
