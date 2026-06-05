"""
Type: Utility
Generate honest ALGO_CALIBRATION_BANDS for DW / RR / RADIO from v3.

calibration_note() in algo_knowledge.py reads the *calibrated* probability and maps
it to a reliability sentence. The production bands existed for DW only (and were
written for the raw, pre-calibration score). This rebuilds all three from the v3
pipeline: cross-validated out-of-fold raw probabilities → apply the stored v3 Platt
calibration → bin → observed positive rate per bin. The emitted (low, high, text)
tuples are pasted into algo_knowledge.py.

Uses: data_anon.csv, train.py, models/v3/calibration.json
Persists in: stdout (Python dict to paste) + analysis/calibration_bands.md
Triggers: manual run `python3 machine_learning/analysis/05_calibration_bands.py`
Depends on: xgboost, scikit-learn
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, cross_val_predict
from xgboost import XGBClassifier

_HERE = os.path.dirname(os.path.abspath(__file__))
_ML = os.path.dirname(_HERE)
sys.path.insert(0, _ML)

from train import FEATURE_COLUMNS, build_dataset  # noqa: E402

DATA_PATH = os.environ.get("ML_TRAIN_DATA", os.path.join(_ML, "01_data", "data_anon.csv"))
CALIB_PATH = os.path.join(_ML, "models", "v3", "calibration.json")
OUT_MD = os.path.join(_HERE, "calibration_bands.md")
RANDOM_STATE = 42
EDGES = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]


def _xgb() -> XGBClassifier:
    return XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05,
                         subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                         random_state=RANDOM_STATE)


def _band_text(lo: float, hi: float, obs: float, n: int) -> str:
    """French reliability sentence comparing predicted band to observed rate."""
    if n < 8:
        return f"Échantillon trop faible (n={n}) — fiabilité non mesurable ici."
    mid = (lo + min(hi, 1.0)) / 2
    obs_pct = f"{obs * 100:.0f}%"
    if obs >= mid + 0.15:
        return f"Sous-estimé : réussite réelle ~{obs_pct} (mieux que le score affiché)."
    if obs <= mid - 0.15:
        return f"⚠️ Sur-confiance : score dans cette bande ne vaut qu'~{obs_pct} de réussite réelle."
    return f"Fiable : score ≈ réalité (réussite observée ~{obs_pct}, n={n})."


def bands_for(y: np.ndarray, p_cal: np.ndarray) -> list:
    """Bin calibrated probabilities; emit (low, high, text) reliability tuples."""
    idx = np.digitize(p_cal, EDGES[1:-1])
    out = []
    for b in range(len(EDGES) - 1):
        lo, hi = EDGES[b], EDGES[b + 1]
        m = idx == b
        n = int(m.sum())
        obs = float(y[m].mean()) if n else 0.0
        out.append((round(lo, 2), round(hi, 2), _band_text(lo, hi, obs, n)))
    return out


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    ds = build_dataset(df.copy())
    groups = df["NameID"].values
    X = ds[FEATURE_COLUMNS]
    platt = json.load(open(CALIB_PATH))
    gkf = GroupKFold(n_splits=5)
    result, lines = {}, ["# Empirical calibration bands (v3, OOF group-CV)\n"]
    for algo, key in (("DW", "dw"), ("RR", "rr"), ("RADIO", "radio")):
        y = ds[f"y_{key}"].values
        oof = cross_val_predict(_xgb(), X, ds[f"y_{key}"], cv=gkf, groups=groups,
                                method="predict_proba")[:, 1]
        c = platt[key]
        p_cal = 1.0 / (1.0 + np.exp(-(c["coef"] * oof + c["intercept"])))
        result[algo] = bands_for(y, p_cal)
        lines.append(f"## {algo}\n")
        for lo, hi, txt in result[algo]:
            lines.append(f"- [{lo}, {hi}) — {txt}")
        lines.append("")
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    print("ALGO_CALIBRATION_BANDS = {")
    for algo, bands in result.items():
        print(f'    "{algo}": [')
        for lo, hi, txt in bands:
            print(f'        ({lo}, {hi}, "{txt}"),')
        print("    ],")
    print("}")
    print(f"\n[written] {OUT_MD}")


if __name__ == "__main__":
    main()
