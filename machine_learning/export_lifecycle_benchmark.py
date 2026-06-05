#!/usr/bin/env python3
"""Export the global algorithmic lifecycle benchmark to seed SQL.

Type: Utility
Uses: data_anon.csv (the anonymized training dataset — NOT committed to the repo)
Persists in: stdout (prints INSERT ... ON CONFLICT to paste into a migration)

Reproduces the user's standardization analysis: for each algorithm (DW / RR /
Radio), each song's ratio = its <algo> 28d streams / the mean of its WEIGHT
CATEGORY (follower decile for DW/RR, popularity bucket for Radio). Ratios are then
aggregated by song-age-in-weeks bin into quartiles, yielding the cohort lifecycle
curves consumed by the "Cycle de vie & Benchmark" dashboard tab.

This script writes NOTHING to the database — it prints ready-to-paste SQL. Run it
once on the real dataset, then drop the output into
migrations/035_algo_lifecycle_benchmark.sql (replacing the provisional seed) and
apply via `make migrate`.

Usage:
    python machine_learning/export_lifecycle_benchmark.py path/to/data_anon.csv [--version v2]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import TARGET_THRESHOLDS  # noqa: E402  (DW>137, RR>130, RADIO>639)

# A song "triggered" an algo when its 28d algo streams clear the elbow threshold. The
# v1 seed pooled ALL songs, so >80% non-triggering zeros crushed the median ratio toward
# 0 (useless benchmark). v2 conditions on the TRIGGERING cohort: the curve answers "among
# songs that DID trigger, how does the lifecycle look?" — and total_stream_median becomes
# meaningful (no longer NULL) so the live standardization overlay has a real reference.
_THRESH = {"DW": TARGET_THRESHOLDS["dw"], "RR": TARGET_THRESHOLDS["rr"],
           "RADIO": TARGET_THRESHOLDS["radio"]}
_MIN_BIN = 5  # skip age bins with fewer triggering songs (noisy quartiles)

# (label, order, lower_week_inclusive, upper_week_exclusive)
AGE_BINS = [
    ("0-5", 1, 0, 5),
    ("5-10", 2, 5, 10),
    ("10-25", 3, 10, 25),
    ("25-50", 4, 25, 50),
    ("50-100", 5, 50, 100),
    ("100+", 6, 100, 10_000),
]

# algorithm -> (28d stream column, weight category column, weight category type)
ALGOS = {
    "DW": ("DiscoverWeeklyStreamsLast28Days", "CurrentSpotifyFollowers", "follower_decile"),
    "RR": ("ReleaseRadarStreamsLast28Days", "CurrentSpotifyFollowers", "follower_decile"),
    "RADIO": ("RadioStreamsLast28Days", "PopularityIndex", "popularity_bucket"),
}

TOTAL_STREAMS_COL = "StreamsLast28Days"  # for the live total-vs-total overlay bridge


def _age_bin(weeks: float):
    for label, order, lo, hi in AGE_BINS:
        if lo <= weeks < hi:
            return label, order
    return None, None


def _weight_buckets(series: pd.Series) -> pd.Series:
    """Decile buckets; falls back to fewer bins if the data has too few unique values."""
    for q in (10, 5, 3):
        try:
            return pd.qcut(series.rank(method="first"), q=q, labels=False, duplicates="drop")
        except (ValueError, IndexError):
            continue
    return pd.Series(0, index=series.index)


def build_rows(df: pd.DataFrame, version: str, condition_on_trigger: bool = True) -> list[dict]:
    df = df.copy()
    df["_age_weeks"] = (df["DaysSinceRelease"].astype(float) / 7.0)
    df[["_bin", "_order"]] = df["_age_weeks"].apply(lambda w: pd.Series(_age_bin(w)))
    df = df.dropna(subset=["_bin"])

    rows: list[dict] = []
    for algo, (stream_col, weight_col, weight_type) in ALGOS.items():
        if stream_col not in df.columns or weight_col not in df.columns:
            print(f"-- WARN: missing column(s) for {algo} ({stream_col}/{weight_col}); skipped",
                  file=sys.stderr)
            continue
        sub = df.dropna(subset=[stream_col, weight_col]).copy()
        if condition_on_trigger:
            # Keep only the triggering cohort (clears the elbow threshold).
            sub = sub[sub[stream_col] > _THRESH[algo]].copy()
            if sub.empty:
                print(f"-- WARN: no triggering songs for {algo}; skipped", file=sys.stderr)
                continue
        sub["_bucket"] = _weight_buckets(sub[weight_col])
        bucket_mean = sub.groupby("_bucket")[stream_col].transform("mean")
        sub["_ratio"] = sub[stream_col] / bucket_mean.replace(0, np.nan)
        sub = sub.dropna(subset=["_ratio"])

        for label, order, _lo, _hi in AGE_BINS:
            g = sub[sub["_bin"] == label]
            if len(g) < _MIN_BIN:
                if not g.empty:
                    print(f"-- skip {algo}/{label}: only {len(g)} triggering songs (<{_MIN_BIN})",
                          file=sys.stderr)
                continue
            r = g["_ratio"]
            total_med = (float(g[TOTAL_STREAMS_COL].median())
                         if TOTAL_STREAMS_COL in g.columns else None)
            rows.append({
                "algorithm": algo,
                "weight_category_type": weight_type,
                "age_week_bin": label,
                "age_week_bin_order": order,
                "ratio_min": round(float(r.min()), 4),
                "ratio_q1": round(float(r.quantile(0.25)), 4),
                "ratio_median": round(float(r.median()), 4),
                "ratio_q3": round(float(r.quantile(0.75)), 4),
                "ratio_max": round(float(r.max()), 4),
                "total_stream_median": (round(total_med, 2) if total_med is not None else None),
                "sample_count": int(len(g)),
                "dataset_version": version,
            })
    return rows


def to_sql(rows: list[dict]) -> str:
    def val(x):
        return "NULL" if x is None else (f"'{x}'" if isinstance(x, str) else str(x))

    cols = ["algorithm", "weight_category_type", "age_week_bin", "age_week_bin_order",
            "ratio_min", "ratio_q1", "ratio_median", "ratio_q3", "ratio_max",
            "total_stream_median", "sample_count", "dataset_version"]
    lines = [f"    ({', '.join(val(row[c]) for c in cols)})" for row in rows]
    update = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in
                       ("algorithm", "age_week_bin", "dataset_version"))
    return (
        f"INSERT INTO algo_lifecycle_benchmark ({', '.join(cols)}) VALUES\n"
        + ",\n".join(lines)
        + f"\nON CONFLICT (algorithm, age_week_bin, dataset_version) DO UPDATE SET\n    {update},\n"
        + "    exported_at = CURRENT_TIMESTAMP;"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", help="path to data_anon.csv")
    ap.add_argument("--version", default="v2", help="dataset_version tag (default: v2)")
    ap.add_argument("--all-songs", action="store_true",
                    help="legacy v1 behaviour: pool ALL songs (medians crushed to ~0)")
    args = ap.parse_args()

    path = Path(args.csv)
    if not path.is_file():
        sys.exit(f"❌ dataset not found: {path} (data_anon.csv is not committed to the repo)")

    df = pd.read_csv(path)
    rows = build_rows(df, args.version, condition_on_trigger=not args.all_songs)
    if not rows:
        sys.exit("❌ no rows produced — check column names in the dataset")
    print(to_sql(rows))


if __name__ == "__main__":
    main()
