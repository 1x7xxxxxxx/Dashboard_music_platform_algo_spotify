"""
Type: Utility
Forward-looking reframe: how much of the classifier's skill is genuine prediction
versus reading concurrent streams that already contain the algorithm's own output?

The production target (DW/RR/Radio streams in the 28-day window) is measured at the
same snapshot as the features. Three features are mechanically derived from streams
that include algo streams (StreamsLast7Days_log, ListenersStreamRatio28Days_adj,
Velocity_Streams) — so a high AUC may partly be "scoring the present". This script
strips those and re-scores, to see what an actionable, genuinely-leading model can do.

Three feature sets, all group-CV (StratifiedGroupKFold by NameID):
  - prod      : the 11-feature production contract (includes concurrent streams)
  - leading   : drop the 3 stream-mechanical features (keep saves/playlist-adds/levers)
  - metadata  : artist + release metadata only (followers, catalogue, cadence, age,
                phase, discovery mode) — the truly pre-trigger, plannable signals

Uses: data_anon.csv, train.py (build_dataset)
Persists in: machine_learning/analysis/forecast.md
Triggers: manual run `python3 machine_learning/analysis/04_forecast_variant.py`
Depends on: xgboost, scikit-learn
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from xgboost import XGBClassifier

_HERE = os.path.dirname(os.path.abspath(__file__))
_ML = os.path.dirname(_HERE)
sys.path.insert(0, _ML)

from train import build_dataset  # noqa: E402

DATA_PATH = os.environ.get("ML_TRAIN_DATA", os.path.join(_ML, "01_data", "data_anon.csv"))
OUT_MD = os.path.join(_HERE, "forecast.md")
RANDOM_STATE = 42
N_SPLITS, N_REPEATS = 5, 3

STREAM_MECHANICAL = ["StreamsLast7Days_log", "ListenersStreamRatio28Days_adj",
                     "Velocity_Streams"]
PROD = ["StreamsLast7Days_log", "CurrentSpotifyFollowers_log",
        "HowManySongsHasThisArtistEverReleased", "IsThisSongOptedIntoSpotifyDiscoveryMode",
        "ReleaseConsistencyNum", "DaysSinceRelease", "ListenersStreamRatio28Days_adj",
        "SavesLast28Days_adj", "PlaylistAddsLast28Days_adj", "ReleasePhaseEarly",
        "Velocity_Streams"]
LEADING = [c for c in PROD if c not in STREAM_MECHANICAL]
METADATA = ["CurrentSpotifyFollowers_log", "HowManySongsHasThisArtistEverReleased",
            "IsThisSongOptedIntoSpotifyDiscoveryMode", "ReleaseConsistencyNum",
            "DaysSinceRelease", "ReleasePhaseEarly"]
FEATURE_SETS = {"prod": PROD, "leading": LEADING, "metadata": METADATA}


def _xgb() -> XGBClassifier:
    return XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05,
                         subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                         random_state=RANDOM_STATE)


def _score(X: pd.DataFrame, y: pd.Series, groups: np.ndarray) -> tuple[float, float]:
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
    return float(np.mean(aucs)), float(np.mean(aps))


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    ds = build_dataset(df.copy())
    groups = df["NameID"].values
    lines = ["# Forward-looking reframe — is the skill real prediction or concurrency?\n",
             "group-CV ROC-AUC / AP by feature set. `prod` includes the 3 "
             "stream-mechanical features; `leading` drops them; `metadata` keeps only "
             "pre-trigger artist/release signals.\n",
             "| algo | prod (11) | leading (8) | metadata (6) |",
             "|---|---|---|---|"]
    for algo in ("dw", "rr", "radio"):
        y = ds[f"y_{algo}"]
        cells = []
        for name in ("prod", "leading", "metadata"):
            auc, ap = _score(ds[FEATURE_SETS[name]], y, groups)
            cells.append(f"{auc:.3f} / {ap:.3f}")
        lines.append(f"| {algo} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines.append("\n*If `leading`/`metadata` stay close to `prod`, the model is "
                 "genuinely forecasting from plannable signals. A large drop means the "
                 "skill was mostly reading streams that already contain the algo output.*\n")
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n[written] {OUT_MD}")


if __name__ == "__main__":
    main()
