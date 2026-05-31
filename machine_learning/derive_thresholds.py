"""
Type: Utility
Empirically derive per-feature success-rate "knees" from data_anon.csv.

The user's SHAP notes contradict each other (and sometimes the encoded
algo_knowledge zones) on a few thresholds (velocity, saves, ratio, catalogue).
Rather than arbitrate between conflicting human notes, this script computes the
objective inflection points from the training data: for each algorithm target
and feature, the success rate per bin, and the value where it first crosses the
base rate (bonus knee) and where it sits well below it (malus ceiling).

Features are built with the EXACT inference definitions (train.build_dataset),
so the derived thresholds are in the same units the live gauges read. Log
features are reported in human (expm1) units.

Uses: machine_learning/01_data/data_anon.csv
Persists in: machine_learning/models/<MODEL_VERSION>/thresholds_derived.json
Triggers: manual run `python3 machine_learning/derive_thresholds.py`
"""
import json
import os

import numpy as np
import pandas as pd

from train import DATA_PATH, FEATURE_COLUMNS, OUT_DIR, build_dataset

# Features reported in raw (expm1) units because they are log-transformed in ds.
_LOG_FEATURES = {"StreamsLast7Days_log", "CurrentSpotifyFollowers_log", "NonAlgoStreams28Days_log"}

# The features whose encoded zones the notes dispute (focus of the reconciliation).
_DISPUTED = {
    "Velocity_Streams", "SavesLast28Days_adj", "PlaylistAddsLast28Days_adj",
    "ListenersStreamRatio28Days_adj", "HowManySongsHasThisArtistEverReleased",
    "CurrentSpotifyFollowers_log", "NonAlgoStreams28Days_log",
}

ALGOS = ("dw", "rr", "radio")
N_BINS = 8


def _human(feature: str, series: pd.Series) -> pd.Series:
    return np.expm1(series) if feature in _LOG_FEATURES else series


def _knees(x: pd.Series, y: pd.Series, base: float):
    """Bin x into quantiles, return (bin_table, bonus_knee, malus_ceiling).

    bonus_knee = lowest bin upper-edge whose success rate >= base and stays >= base.
    malus_ceiling = highest bin upper-edge whose success rate < 0.6*base from the bottom.
    """
    try:
        bins = pd.qcut(x.rank(method="first"), q=N_BINS, labels=False)
    except ValueError:
        return [], None, None
    table = []
    for b in range(N_BINS):
        m = bins == b
        if not m.any():
            continue
        rate = float(y[m].mean())
        table.append({"lo": round(float(x[m].min()), 2), "hi": round(float(x[m].max()), 2),
                      "n": int(m.sum()), "rate": round(rate, 3)})
    # bonus knee: first bin (low→high) at/above base with all later bins also >= base*0.9
    bonus = None
    for i, row in enumerate(table):
        if row["rate"] >= base and all(r["rate"] >= base * 0.85 for r in table[i:]):
            bonus = row["lo"]
            break
    # malus ceiling: contiguous low bins below 0.6*base
    malus = None
    for row in table:
        if row["rate"] < 0.6 * base:
            malus = row["hi"]
        else:
            break
    return table, bonus, malus


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    ds = build_dataset(df.copy())
    out = {}
    for algo in ALGOS:
        y = ds[f"y_{algo}"]
        base = float(y.mean())
        print(f"\n===== {algo.upper()} (base success rate = {base:.1%}, n={len(y)}) =====")
        out[algo] = {"base_rate": round(base, 3), "features": {}}
        for feat in FEATURE_COLUMNS:
            x = _human(feat, ds[feat])
            table, bonus, malus = _knees(x, y, base)
            out[algo]["features"][feat] = {"bonus_knee": bonus, "malus_ceiling": malus, "bins": table}
            flag = " *" if feat in _DISPUTED else ""
            print(f"  {feat:38s} malus<= {str(malus):>10}  bonus>= {str(bonus):>10}{flag}")
    path = os.path.join(OUT_DIR, "thresholds_derived.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n✅ Wrote {path}  (* = note-disputed feature)")


if __name__ == "__main__":
    main()
