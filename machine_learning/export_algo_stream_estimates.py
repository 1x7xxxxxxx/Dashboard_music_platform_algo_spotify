"""What an algorithm brings once it has triggered — P25/P50/P75 by age, from the training set.

Type: Utility
Uses: machine_learning/01_data/data_anon.csv (training set, local), train.TARGET_THRESHOLDS
Triggers: run by hand after a retrain: `python machine_learning/export_algo_stream_estimates.py`
Persists in: machine_learning/models/v3/algo_stream_estimates.json (aggregates only, versioned)

R247 (fiche 43, owner 2026-09-27 : « combien de streams ça peut nous rapporter si on trigger
les algos, estimation J+28, J+6 mois, J+1 an » — arbitrated: « jeu d'entraînement »).

WHAT IT IS, AND WHAT IT IS NOT. Each row of the training set is ONE snapshot of ONE song at
ONE age, with its last-28-day algorithmic streams. There is no series per song. So the
estimate at « 6 months » is the 28-day algo volume of OTHER songs that were 6 months old
when snapshotted and had triggered — a monthly RATE at that age, cross-sectional, never a
cumul and never this song's future. « Triggered » is the training label (`TARGET_THRESHOLDS`:
DW>137, RR>130, Radio>639 streams over 28 days) — the definition the sibling script
`export_lifecycle_benchmark.py` settled on after `> 0` crushed the quartiles with near-zero
songs (code-critic, R247). A cell with fewer than `MIN_N` songs is written as refused.

R601 (owner, 2026-10-15 : « Release Radar ne retombe pas après le 1er mois ») — conditioning
on « triggered at that age » made an age where NO song triggers look like an age with too
few songs: Release Radar at 6 months and 1 year came out `refused`, the curve stopped at
J+28 and the fall was never drawn. Measured on data_anon.csv: of the 244 rows older than
90 days, none has a single Release Radar stream — the playlist is weekly and ends. When
the triggered cell is short but the WHOLE age bucket has `MIN_N` songs, all at zero, the
cell is a measured zero (`zero: True`), not a refusal.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def _train_thresholds() -> dict:
    """`TARGET_THRESHOLDS` read from train.py's AST — the SAME definition, without importing
    the training stack (imblearn, xgboost…) the app environment does not carry."""
    tree = ast.parse((HERE / "train.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "TARGET_THRESHOLDS"
                                                 for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit("TARGET_THRESHOLDS absent de train.py")


TARGET_THRESHOLDS = _train_thresholds()

DATA = HERE / "01_data" / "data_anon.csv"
OUT = HERE / "models" / "v3" / "algo_stream_estimates.json"
MIN_N = 10   # the sibling uses 5 for a benchmark band; an artist-facing number asks more
AGES = {"j28": (0, 45), "m6": (150, 210), "y1": (330, 400)}
COLUMNS = {"dw": "DiscoverWeeklyStreamsLast28Days", "rr": "ReleaseRadarStreamsLast28Days",
           "radio": "RadioStreamsLast28Days"}


def estimates(d: pd.DataFrame) -> dict:
    """{algo: {age: {p25, p50, p75, n} | {n, refused: True}}}. Pure."""
    out = {}
    for algo, col in COLUMNS.items():
        trig = d[pd.to_numeric(d[col], errors="coerce") > TARGET_THRESHOLDS[algo]]
        out[algo] = {}
        for age, (lo, hi) in AGES.items():
            part = trig[(trig["DaysSinceRelease"] >= lo) & (trig["DaysSinceRelease"] <= hi)][col]
            n = int(part.notna().sum())
            if n < MIN_N:
                every = pd.to_numeric(d[(d["DaysSinceRelease"] >= lo)
                                        & (d["DaysSinceRelease"] <= hi)][col], errors="coerce")
                every = every.dropna()
                out[algo][age] = ({"p25": 0.0, "p50": 0.0, "p75": 0.0, "n": int(len(every)),
                                   "zero": True}
                                  if len(every) >= MIN_N and (every == 0).all()
                                  else {"n": n, "refused": True})
                continue
            q = part.quantile([0.25, 0.5, 0.75]).round(0)
            out[algo][age] = {"p25": float(q[0.25]), "p50": float(q[0.5]),
                              "p75": float(q[0.75]), "n": n}
    return out


if __name__ == "__main__":
    res = {"source": "machine_learning/01_data/data_anon.csv", "rows": 0,
           "unit": "streams algorithmiques sur 28 jours, titres déclenchés, à cet âge",
           "thresholds": TARGET_THRESHOLDS, "min_n": MIN_N,
           "ages_days": {k: list(v) for k, v in AGES.items()}}
    frame = pd.read_csv(DATA)
    res["rows"] = len(frame)
    res["estimates"] = estimates(frame)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res["estimates"], ensure_ascii=False))
