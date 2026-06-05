"""
Type: Utility
Honest group-CV validation of the Popularity Index (PI) regressor.

The PI model's R²=0.94 was measured on a single random split. PI is highly correlated
with streams, and the same song appears multiple times in data_anon.csv, so a random
split is optimistic. This re-measures R² + MAE with GroupKFold by NameID — the number
the dashboard should quote. It writes the verdict to metrics.json (pi block) so the UI
help text can stop saying "non revalidé".

Uses: data_anon.csv, train.py (PI_FEATURES)
Persists in: machine_learning/analysis/pi_validation.md + models/v3/metrics.json (pi block)
Triggers: manual run `python3 machine_learning/analysis/08_validate_pi.py`
Depends on: xgboost, scikit-learn
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from xgboost import XGBRegressor

_HERE = os.path.dirname(os.path.abspath(__file__))
_ML = os.path.dirname(_HERE)
sys.path.insert(0, _ML)

from train import PI_FEATURES  # noqa: E402

DATA_PATH = os.environ.get("ML_TRAIN_DATA", os.path.join(_ML, "01_data", "data_anon.csv"))
METRICS_PATH = os.path.join(_ML, "models", "v3", "metrics.json")
OUT_MD = os.path.join(_HERE, "pi_validation.md")
RANDOM_STATE = 42
N_SPLITS = 5


def _pi() -> XGBRegressor:
    return XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05,
                        random_state=RANDOM_STATE)


def main() -> None:
    df = pd.read_csv(DATA_PATH).dropna(subset=["PopularityIndex", *PI_FEATURES])
    X, y = df[PI_FEATURES], df["PopularityIndex"]
    groups = df["NameID"].values
    r2s, maes = [], []
    gkf = GroupKFold(n_splits=N_SPLITS)
    for tr, te in gkf.split(X, y, groups):
        reg = _pi().fit(X.iloc[tr], y.iloc[tr])
        pred = np.clip(reg.predict(X.iloc[te]), 0, 100)
        r2s.append(r2_score(y.iloc[te], pred))
        maes.append(mean_absolute_error(y.iloc[te], pred))
    q = lambda a, x: round(float(np.quantile(a, x)), 3)  # noqa: E731
    pi_block = {"r2_groupcv": round(float(np.mean(r2s)), 3),
                "r2_ci": [q(r2s, 0.025), q(r2s, 0.975)],
                "mae_groupcv": round(float(np.mean(maes)), 2),
                "features": PI_FEATURES, "eval": "GroupKFold by NameID",
                "note": "PI is highly stream-correlated; group-CV is the honest number."}

    lines = ["# PI regressor — honest group-CV validation\n",
             f"GroupKFold({N_SPLITS}) by `NameID`, n={len(df)}.\n",
             f"- **R² (group-CV)**: {pi_block['r2_groupcv']} "
             f"[{pi_block['r2_ci'][0]}–{pi_block['r2_ci'][1]}]",
             f"- **MAE (group-CV)**: {pi_block['mae_groupcv']} points de PI",
             "\n*Compare to the single-split R²~0.94: group-CV is the trustworthy figure.*"]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))

    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH) as f:
            metrics = json.load(f)
        metrics["pi"] = pi_block
        with open(METRICS_PATH, "w") as f:
            json.dump(metrics, f, indent=2)
    print("\n".join(lines))
    print(f"\n[written] {OUT_MD} + metrics.json pi block")


if __name__ == "__main__":
    main()
