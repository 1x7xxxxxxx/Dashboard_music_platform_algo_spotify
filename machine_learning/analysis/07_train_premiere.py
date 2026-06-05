"""
Type: Utility
Train + persist the pre-release Release Radar estimator (the flagship discovery).

forecast.md §5 showed RR keeps AUC ~0.92 from RELEASE-DAY metadata ALONE (no streams):
followers, catalogue size, release cadence, days-since-release, release phase, discovery
mode. That means RR odds can be estimated BEFORE a single stream lands — a planning tool.
This script trains exactly that metadata-only RR classifier and saves it as a v3 artifact
so `ml_inference.estimate_rr_prerelease()` can serve it.

Same rigor as the main pipeline: group-CV by NameID for the reported metric, no SMOTE,
Platt calibration fit on out-of-fold predictions (not the test split).

Uses: data_anon.csv, train.py (build_dataset)
Persists in: machine_learning/models/v3/rr_premiere_classifier.ubj + premiere.json
Triggers: manual run `python3 machine_learning/analysis/07_train_premiere.py`
Depends on: xgboost, scikit-learn
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import (
    GroupKFold,
    StratifiedGroupKFold,
    cross_val_predict,
)
from xgboost import XGBClassifier

_HERE = os.path.dirname(os.path.abspath(__file__))
_ML = os.path.dirname(_HERE)
sys.path.insert(0, _ML)

from train import build_dataset  # noqa: E402

DATA_PATH = os.environ.get("ML_TRAIN_DATA", os.path.join(_ML, "01_data", "data_anon.csv"))
OUT_DIR = os.path.join(_ML, "models", "v3")
RANDOM_STATE = 42
N_SPLITS, N_REPEATS = 5, 3

# Release-day-knowable features only (no stream-derived signal). Order is the serving
# contract used by ml_inference.estimate_rr_prerelease().
PREMIERE_FEATURES = [
    "CurrentSpotifyFollowers_log",
    "HowManySongsHasThisArtistEverReleased",
    "IsThisSongOptedIntoSpotifyDiscoveryMode",
    "ReleaseConsistencyNum",
    "DaysSinceRelease",
    "ReleasePhaseEarly",
]


def _xgb() -> XGBClassifier:
    return XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05,
                         subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                         random_state=RANDOM_STATE)


def _cv_band(X, y, groups) -> dict:
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
    q = lambda a, x: round(float(np.quantile(a, x)), 3)  # noqa: E731
    return {"auc": round(float(np.mean(aucs)), 3), "auc_ci": [q(aucs, 0.025), q(aucs, 0.975)],
            "ap": round(float(np.mean(aps)), 3)}


def _platt_oof(X, y, groups) -> dict:
    oof = cross_val_predict(_xgb(), X, y, cv=GroupKFold(N_SPLITS), groups=groups,
                            method="predict_proba")[:, 1]
    lr = LogisticRegression().fit(oof.reshape(-1, 1), y)
    return {"coef": float(lr.coef_[0, 0]), "intercept": float(lr.intercept_[0])}


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(DATA_PATH)
    ds = build_dataset(df.copy())
    groups = df["NameID"].values
    X, y = ds[PREMIERE_FEATURES], ds["y_rr"]

    metrics = _cv_band(X, y, groups)
    calibration = _platt_oof(X, y, groups)
    clf = _xgb().fit(X, y)
    clf.save_model(os.path.join(OUT_DIR, "rr_premiere_classifier.ubj"))

    payload = {"features": PREMIERE_FEATURES, "calibration": calibration,
               "cv": metrics, "positives": int(y.sum()), "n": int(len(y)),
               "note": "Release-day metadata-only RR estimator (no streams). "
                       "group-CV by NameID, OOF-Platt calibration."}
    with open(os.path.join(OUT_DIR, "premiere.json"), "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[premiere] RR metadata-only  AUC={metrics['auc']} "
          f"CI={metrics['auc_ci']}  AP={metrics['ap']}  "
          f"calib={calibration}  -> {OUT_DIR}/rr_premiere_classifier.ubj + premiere.json")


if __name__ == "__main__":
    main()
