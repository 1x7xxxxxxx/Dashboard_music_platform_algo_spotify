#!/usr/bin/env python3
"""Export per-algo reliability (calibration) bands from the SAVED classifiers.

Type: Utility
Uses: machine_learning/01_data/data_anon.csv + models/v2_noscaler/*_classifier.ubj
      + models/v2_noscaler/calibration.json (Platt params)
Persists in: stdout (prints a Python dict to paste into
             src/dashboard/utils/algo_knowledge.py::ALGO_CALIBRATION_BANDS)

Loads the deployed classifiers (does NOT retrain — leaves models/ untouched),
reproduces the exact held-out test split used by train.py (same RANDOM_STATE /
stratify / TEST_SIZE), applies the stored Platt calibration, then bins the
calibrated probabilities into 5 buckets and reports the observed positive rate +
count per bucket. This is the numeric form of the calibration curve.

Usage:
    python3 machine_learning/export_calibration_bands.py [--algos rr radio]
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from train import DATA_PATH, FEATURE_COLUMNS, RANDOM_STATE, TEST_SIZE, build_dataset

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(_HERE, "models", "v2_noscaler")
BIN_EDGES = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def bands_for(algo: str, ds: pd.DataFrame, platt: dict) -> list[dict]:
    X, y = ds[FEATURE_COLUMNS], ds[f"y_{algo}"]
    _, Xte, _, yte = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    clf = XGBClassifier()
    clf.load_model(os.path.join(OUT_DIR, f"{algo}_classifier.ubj"))
    p_raw = clf.predict_proba(Xte)[:, 1]
    cal = platt.get(algo)
    p = _sigmoid(cal["coef"] * p_raw + cal["intercept"]) if cal else p_raw

    yte = yte.to_numpy()
    bins = []
    for lo, hi in zip(BIN_EDGES[:-1], BIN_EDGES[1:]):
        mask = (p >= lo) & (p < hi) if hi < 1.0 else (p >= lo) & (p <= hi)
        n = int(mask.sum())
        if n == 0:
            continue
        bins.append({
            "p_pred": round(float(p[mask].mean()), 3),
            "p_obs": round(float(yte[mask].mean()), 3),
            "n": n,
        })
    return bins


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--algos", nargs="+", default=["rr", "radio"])
    args = ap.parse_args()

    df = pd.read_csv(DATA_PATH)
    ds = build_dataset(df.copy())
    with open(os.path.join(OUT_DIR, "calibration.json")) as f:
        platt = json.load(f)

    out = {}
    for algo in args.algos:
        out[algo.upper()] = {
            "bins": bands_for(algo, ds, platt),
            "source": f"export_calibration_bands.py ({algo}_classifier.ubj, Platt-calibrated test split)",
        }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
