"""
Type: Utility
Independent data audit of data_anon.csv, written from scratch as the first phase
of an independent ML re-derivation (full-takeover comparison vs train.py).

It does NOT train anything. It interrogates the data for the structural risks that
decide whether the existing single-split metrics are trustworthy:
  1. Row-grouping: does a song (NameID) appear in multiple rows? -> random splits leak.
  2. Concurrency/leakage: how much of StreamsLast7Days is itself algo streams that
     overlap the prediction target?
  3. Target sensitivity: are the 137/130/639 binarization thresholds knees or arbitrary?
  4. Data quality: negatives, missingness, categorical cardinality.
  5. Serve skew: the two features imputed-to-0 at inference vs their training spread.

Uses: machine_learning/01_data/data_anon.csv, machine_learning/train.py (build_dataset)
Persists in: machine_learning/analysis/audit.md
Triggers: manual run `python3 machine_learning/analysis/01_audit.py`
Depends on: pandas, numpy, scikit-learn
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif

_HERE = os.path.dirname(os.path.abspath(__file__))
_ML = os.path.dirname(_HERE)
sys.path.insert(0, _ML)

from train import (  # noqa: E402  (path insert must precede import)
    FEATURE_COLUMNS,
    TARGET_THRESHOLDS,
    build_dataset,
)

DATA_PATH = os.environ.get("ML_TRAIN_DATA", os.path.join(_ML, "01_data", "data_anon.csv"))
OUT_MD = os.path.join(_HERE, "audit.md")

# 7-day algo stream columns that structurally overlap StreamsLast7Days.
_ALGO_7D = ["DiscoverWeeklyStreamsLast7Days", "ReleaseRadarStreamsLast7Days",
            "RadioStreamsLast7Days"]
_TARGET_COL = {"dw": "DiscoverWeeklyStreamsLast28Days",
               "rr": "ReleaseRadarStreamsLast28Days",
               "radio": "RadioStreamsLast28Days"}


def section_grouping(df: pd.DataFrame, lines: list[str]) -> None:
    """Quantify song-identity duplication that would leak across a random split."""
    lines.append("## 1. Row grouping (leakage risk on random splits)\n")
    n_rows = len(df)
    for key in ("NameID", "EntryID"):
        if key not in df.columns:
            lines.append(f"- `{key}`: **absent**\n")
            continue
        n_unique = df[key].nunique()
        dup_rows = n_rows - n_unique
        lines.append(f"- `{key}`: {n_unique} unique / {n_rows} rows "
                     f"({dup_rows} duplicate rows, {dup_rows / n_rows:.1%})")
    if "NameID" in df.columns:
        counts = df["NameID"].value_counts()
        multi = counts[counts > 1]
        lines.append(f"- Songs appearing >1×: **{len(multi)}** "
                     f"(max {int(counts.max())} snapshots for one song)")
        verdict = ("GROUP-SPLIT REQUIRED — same song can land in train+test"
                   if len(multi) else "random split is safe (no song duplication)")
        lines.append(f"- **Verdict:** {verdict}\n")


def section_leakage(df: pd.DataFrame, ds: pd.DataFrame, lines: list[str]) -> None:
    """Show how much of the 7-day stream feature is concurrent algo signal."""
    lines.append("## 2. Concurrency / target leakage\n")
    s7 = df["StreamsLast7Days"].fillna(0).clip(lower=0)
    algo7 = df[_ALGO_7D].fillna(0).clip(lower=0).sum(axis=1)
    share = np.where(s7 > 0, algo7 / s7, 0.0)
    lines.append(f"- `StreamsLast7Days` median algo share: **{np.median(share):.1%}** "
                 f"(mean {np.mean(share):.1%}). A top model feature is partly the "
                 f"thing being predicted.")
    lines.append("\n| target | MI(StreamsLast7Days_log) | top-3 features by MI |")
    lines.append("|---|---|---|")
    for algo in ("dw", "rr", "radio"):
        y = ds[f"y_{algo}"].values
        mi = mutual_info_classif(ds[FEATURE_COLUMNS], y, random_state=0)
        mi_s = pd.Series(mi, index=FEATURE_COLUMNS).sort_values(ascending=False)
        top3 = ", ".join(f"{f}={v:.3f}" for f, v in mi_s.head(3).items())
        lines.append(f"| {algo} | {mi_s['StreamsLast7Days_log']:.3f} | {top3} |")
    lines.append("")


def section_target_sensitivity(df: pd.DataFrame, lines: list[str]) -> None:
    """Sweep the binarization thresholds to test whether they are knees."""
    lines.append("## 3. Target threshold sensitivity\n")
    lines.append("| algo | thr×0.5 | thr (prod) | thr×1.5 | thr×2 |")
    lines.append("|---|---|---|---|---|")
    for algo, col in _TARGET_COL.items():
        base = TARGET_THRESHOLDS[algo]
        vals = df[col].fillna(0)
        rates = [f"{(vals > base * m).mean():.1%}" for m in (0.5, 1.0, 1.5, 2.0)]
        lines.append(f"| {algo} (thr={base}) | {rates[0]} | **{rates[1]}** | "
                     f"{rates[2]} | {rates[3]} |")
    lines.append("\n*Positive-class rate at each threshold. A flat region around the "
                 "prod threshold = a stable knee; a steep slope = an arbitrary cut.*\n")


def section_quality(df: pd.DataFrame, lines: list[str]) -> None:
    """Flag negatives, missingness, and categorical cardinality."""
    lines.append("## 4. Data quality\n")
    neg = {c: int((df[c] < 0).sum()) for c in df.select_dtypes("number").columns
           if (df[c] < 0).any()}
    lines.append(f"- Columns with negative values: {neg or 'none'}")
    miss = {c: int(df[c].isnull().sum()) for c in df.columns if df[c].isnull().any()}
    lines.append(f"- Columns with missing values: {miss or 'none'}")
    cats = df.select_dtypes("object").columns
    card = {c: int(df[c].nunique()) for c in cats}
    lines.append(f"- Categorical cardinality: {card}\n")


def section_serve_skew(df: pd.DataFrame, ds: pd.DataFrame, lines: list[str]) -> None:
    """Compare the two imputed-to-0 features' training spread to their served constant."""
    lines.append("## 5. Train/serve skew (features imputed to 0 at inference)\n")
    lines.append("| feature | % rows non-zero in training | training median (non-zero) |")
    lines.append("|---|---|---|")
    for raw, feat in (("NonAlgoStreams28Days", "NonAlgoStreams28Days_log"),
                      ("HowManySongsDoYouHaveInRadioRightNow",
                       "HowManySongsDoYouHaveInRadioRightNow")):
        v = df[raw].fillna(0).clip(lower=0)
        nz = v[v > 0]
        pct = len(nz) / len(v)
        med = nz.median() if len(nz) else 0.0
        lines.append(f"| {feat} | **{pct:.1%}** | {med:,.0f} |")
    lines.append("\n*At inference both collapse to 0. The higher the non-zero %, the "
                 "more the served model runs off the distribution it learned.*\n")


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    ds = build_dataset(df.copy())
    lines = ["# Independent data audit — `data_anon.csv`\n",
             f"Rows: **{len(df)}**, columns: **{df.shape[1]}**. "
             f"Generated by `analysis/01_audit.py` (no training).\n"]
    section_grouping(df, lines)
    section_leakage(df, ds, lines)
    section_target_sensitivity(df, lines)
    section_quality(df, lines)
    section_serve_skew(df, ds, lines)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n[written] {OUT_MD}")


if __name__ == "__main__":
    main()
