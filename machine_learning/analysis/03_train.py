"""
Type: Utility
Independent modeling phase: decide the honest production feature contract and the
champion estimator, then train the final v3 artifacts.

Key decisions it informs:
  1. Cost of dropping the two never-served features (NonAlgoStreams28Days_log,
     HowManySongsDoYouHaveInRadioRightNow). A model that never sees them in
     production should not be trained on them either — this measures the AUC price
     of removing the train/serve skew at its root.
  2. Champion estimator on the production feature set: XGBoost vs HistGradientBoosting
     vs a scaled LogisticRegression baseline, under group-CV.
  3. Volume regressors: can a log-target transform rescue RR volume, judged by R² on
     the original scale under group-CV?

It then trains the final v3 classifiers (imbalance=none, Platt calibration fit on
out-of-fold predictions — the honest version of train.py's fit-on-test), regressors
and PI, and writes models/v3/ with the same artifact layout ml_inference expects.

Uses: data_anon.csv, train.py (build_dataset, FEATURE_COLUMNS, PI_FEATURES, _reg, etc.)
Persists in: machine_learning/models/v3/*, machine_learning/analysis/modeling.md
Triggers: manual run `python3 machine_learning/analysis/03_train.py`
Depends on: xgboost, scikit-learn
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, r2_score, roc_auc_score
from sklearn.model_selection import (
    StratifiedGroupKFold,
    cross_val_predict,
    GroupKFold,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor

_HERE = os.path.dirname(os.path.abspath(__file__))
_ML = os.path.dirname(_HERE)
sys.path.insert(0, _ML)

from train import (  # noqa: E402
    FEATURE_COLUMNS,
    PI_FEATURES,
    build_dataset,
    export_threshold_tables,
)

DATA_PATH = os.environ.get("ML_TRAIN_DATA", os.path.join(_ML, "01_data", "data_anon.csv"))
OUT_DIR = os.path.join(_ML, "models", "v3")
OUT_MD = os.path.join(_HERE, "modeling.md")
RANDOM_STATE = 42
N_SPLITS, N_REPEATS = 5, 3

# The two features with no live source. §A measures the cost of dropping them, but
# the SHIPPED contract keeps all 13 (user decision 2026-06-05: revisit at Phase 2,
# when live NonAlgoStreams + RadioCount sources remove the imputation). The other
# methodology wins (no SMOTE, OOF calibration, log regressors) still apply.
DROP_NO_SOURCE = ["NonAlgoStreams28Days_log", "HowManySongsDoYouHaveInRadioRightNow"]
PROD_FEATURES = [c for c in FEATURE_COLUMNS if c not in DROP_NO_SOURCE]
SHIP_FEATURES = FEATURE_COLUMNS  # 13-feature contract, unchanged vs v2


def _xgb_clf() -> XGBClassifier:
    return XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05,
                         subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                         random_state=RANDOM_STATE)


def _group_scores(make, X, y, groups) -> tuple[float, float]:
    """Mean ROC-AUC & AP over repeated StratifiedGroupKFold for a fresh estimator."""
    aucs, aps = [], []
    for rep in range(N_REPEATS):
        sgk = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True,
                                   random_state=RANDOM_STATE + rep)
        for tr, te in sgk.split(X, y, groups):
            est = make()
            est.fit(X.iloc[tr], y.iloc[tr])
            p = est.predict_proba(X.iloc[te])[:, 1]
            if y.iloc[te].nunique() > 1:
                aucs.append(roc_auc_score(y.iloc[te], p))
                aps.append(average_precision_score(y.iloc[te], p))
    return float(np.mean(aucs)), float(np.mean(aps))


def section_feature_cost(ds, groups, lines: list[str]) -> None:
    """AUC/AP price of dropping the two never-served features."""
    lines.append("## A. Cost of dropping the two never-served features\n")
    lines.append("| algo | full 13-feat ROC-AUC / AP | prod 11-feat ROC-AUC / AP | ΔROC-AUC |")
    lines.append("|---|---|---|---|")
    for algo in ("dw", "rr", "radio"):
        y = ds[f"y_{algo}"]
        a_full, p_full = _group_scores(_xgb_clf, ds[FEATURE_COLUMNS], y, groups)
        a_prod, p_prod = _group_scores(_xgb_clf, ds[PROD_FEATURES], y, groups)
        lines.append(f"| {algo} | {a_full:.3f} / {p_full:.3f} | "
                     f"{a_prod:.3f} / {p_prod:.3f} | **{a_prod - a_full:+.3f}** |")
    lines.append("\n*The 11-feature number is what production can actually deliver "
                 "(no skew). The full-13 number is the offline mirage when the two "
                 "imputed-to-0 features are present.*\n")


def section_champion(ds, groups, lines: list[str]) -> None:
    """Estimator bake-off on the production feature set."""
    lines.append("## B. Champion estimator (production 11 features, group-CV)\n")
    lines.append("| algo | XGBoost | HistGB | LogReg (scaled) |")
    lines.append("|---|---|---|---|")
    makers = {
        "XGBoost": _xgb_clf,
        "HistGB": lambda: HistGradientBoostingClassifier(
            max_depth=4, learning_rate=0.05, max_iter=300, random_state=RANDOM_STATE),
        "LogReg": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=1000, C=1.0)),
    }
    for algo in ("dw", "rr", "radio"):
        y = ds[f"y_{algo}"]
        cells = []
        for _, mk in makers.items():
            auc, ap = _group_scores(mk, ds[PROD_FEATURES], y, groups)
            cells.append(f"{auc:.3f} / {ap:.3f}")
        lines.append(f"| {algo} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines.append("\n*Cells: ROC-AUC / AP. Picking XGBoost unless a simpler model "
                 "matches it within the CI (then prefer the simpler, better-calibrated one).*\n")


def section_regressors(ds, groups, lines: list[str]) -> None:
    """Volume regressors: raw target vs log target, group-CV R² on original scale."""
    lines.append("## C. Volume regressors — raw vs log target (group-CV R², prod feats)\n")
    lines.append("| algo | raw-target R² | log-target R² |")
    lines.append("|---|---|---|")
    gkf = GroupKFold(n_splits=N_SPLITS)
    X = ds[PROD_FEATURES]
    for algo in ("dw", "rr", "radio"):
        y = ds[f"v_{algo}"]
        raw_r2, log_r2 = [], []
        for tr, te in gkf.split(X, y, groups):
            reg = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05,
                               subsample=0.9, colsample_bytree=0.9, random_state=RANDOM_STATE)
            reg.fit(X.iloc[tr], y.iloc[tr])
            raw_r2.append(r2_score(y.iloc[te], reg.predict(X.iloc[te])))
            regl = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05,
                                subsample=0.9, colsample_bytree=0.9, random_state=RANDOM_STATE)
            regl.fit(X.iloc[tr], np.log1p(y.iloc[tr]))
            pred = np.expm1(regl.predict(X.iloc[te])).clip(min=0)
            log_r2.append(r2_score(y.iloc[te], pred))
        lines.append(f"| {algo} | {np.mean(raw_r2):.3f} | {np.mean(log_r2):.3f} |")
    lines.append("\n*R² < 0 means worse than predicting the mean. Use this to decide "
                 "which volume forecasts are honest enough to surface.*\n")


def _platt_oof(clf_maker, X, y, groups) -> dict:
    """Fit Platt params on out-of-fold raw probabilities (honest calibration)."""
    gkf = GroupKFold(n_splits=N_SPLITS)
    oof = cross_val_predict(clf_maker(), X, y, cv=gkf, groups=groups,
                            method="predict_proba")[:, 1]
    lr = LogisticRegression().fit(oof.reshape(-1, 1), y)
    return {"coef": float(lr.coef_[0, 0]), "intercept": float(lr.intercept_[0])}


def train_final(ds, df, groups) -> None:
    """Train + persist the v3 artifacts on the shipped 13-feature contract."""
    os.makedirs(OUT_DIR, exist_ok=True)
    X = ds[SHIP_FEATURES]
    calibration, importance, clf_metrics = {}, {}, {}
    for algo in ("dw", "rr", "radio"):
        y = ds[f"y_{algo}"]
        auc, ap = _group_scores(_xgb_clf, X, y, groups)
        clf = _xgb_clf().fit(X, y)
        clf.save_model(os.path.join(OUT_DIR, f"{algo}_classifier.ubj"))
        calibration[algo] = _platt_oof(_xgb_clf, X, y, groups)
        ranking = sorted(zip(SHIP_FEATURES, clf.feature_importances_),
                         key=lambda t: t[1], reverse=True)
        importance[algo] = [{"feature": f, "gain": round(float(g), 4)} for f, g in ranking]
        clf_metrics[algo] = {"roc_auc_cv": round(auc, 3), "ap_cv": round(ap, 3),
                             "positives": int(y.sum()), "n": int(len(y))}
    reg_metrics = {}
    for algo in ("dw", "rr", "radio"):
        y = ds[f"v_{algo}"]
        reg = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05,
                           subsample=0.9, colsample_bytree=0.9, random_state=RANDOM_STATE)
        reg.fit(X, np.log1p(y))  # log-target: honest floor, never negative
        reg.save_model(os.path.join(OUT_DIR, f"{algo}_regressor.ubj"))
        reg_metrics[algo] = {"target": "log1p", "note": "predict expm1(...)"}
    _train_pi(df)
    stats = {c: {"mean": round(float(X[c].mean()), 4), "std": round(float(X[c].std()), 4),
                 "min": round(float(X[c].min()), 4), "max": round(float(X[c].max()), 4)}
             for c in SHIP_FEATURES}
    metrics = {"model_version": "v3", "rows": int(len(df)), "features": SHIP_FEATURES,
               "classifiers": clf_metrics, "regressors": reg_metrics,
               "feature_stats": stats,
               "imputed_at_serving": DROP_NO_SOURCE,
               "skew_note": "13-feature contract kept; these 2 are imputed to 0 at "
                            "serving until Phase-2 live sources exist (UI shows caveat)."}
    thresholds = export_threshold_tables(df.copy())
    for name, obj in (("metrics.json", metrics), ("calibration.json", calibration),
                      ("feature_importance.json", importance),
                      ("threshold_tables.json", thresholds),
                      ("lime_background.json", X.round(4).values.tolist())):
        with open(os.path.join(OUT_DIR, name), "w") as f:
            json.dump(obj, f, indent=2)


def _train_pi(df: pd.DataFrame) -> None:
    sub = df.dropna(subset=["PopularityIndex", *PI_FEATURES]).copy()
    pi = XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05,
                      random_state=RANDOM_STATE)
    pi.fit(sub[PI_FEATURES], sub["PopularityIndex"])
    pi.save_model(os.path.join(OUT_DIR, "pi_regressor.ubj"))


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    ds = build_dataset(df.copy())
    groups = df["NameID"].values
    lines = ["# Independent modeling — feature contract, champion, regressors\n",
             f"Production feature contract drops {DROP_NO_SOURCE} (no live source). "
             f"group-CV = StratifiedGroupKFold({N_SPLITS})×{N_REPEATS} by NameID.\n"]
    section_feature_cost(ds, groups, lines)
    section_champion(ds, groups, lines)
    section_regressors(ds, groups, lines)
    train_final(ds, df, groups)
    lines.append(f"## D. Final artifacts\n\nTrained v3 (**13-feature** shipped "
                 f"contract per user decision; §A/§B remain the 11-feat analysis), "
                 f"log-target regressors, no SMOTE, OOF-Platt calibration -> "
                 f"`{OUT_DIR}`\n")
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n[written] {OUT_MD} + models/v3/")


if __name__ == "__main__":
    main()
