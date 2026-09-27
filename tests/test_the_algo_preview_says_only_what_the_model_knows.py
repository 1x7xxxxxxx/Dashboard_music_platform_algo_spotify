"""The free Road to Algo preview shows gaps and actions — never a probability the model does not
hold, never a budget without a cost to base it on.

Type: Sub
Uses: src/dashboard/views/algo_preview.py (compose), src/dashboard/utils/algo_preview_data.py
Depends on: nothing (calibration.json is read by sur_le_plancher; no DB)
Persists in: nothing

R193 (2026-09-26). On production that day every probability sat on the calibration floor. The
preview is the first screen a visitor sees of what Premium does; code-critic required it to
show « pas encore d'estimation fiable » instead of a percentage a newcomer would read as real,
and to fold the budget into ONE figure from the 7-day stream gap (the Premium panel's path).
"""
from __future__ import annotations

import math

from src.dashboard.utils.algo_preview_data import sur_le_plancher
from src.dashboard.views import algo_preview as ap

# Stored as the model sees it: log1p, decoded by `expm1` (algo_knowledge json_key). 500 is far
# below the 2 000 streams/7 days target of every algorithm.
_FEATS = {"StreamsLast7Days_log": math.log1p(500)}


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """A floor probability is hidden (None), a strong one shown; the budget is gap × cost,
    one figure; without a cost there is no budget; without a prediction nothing is invented."""
    floor = {"dw_probability": 0.065, "rr_probability": 0.065, "radio_probability": 0.107}
    assert all(sur_le_plancher(a, floor[f"{a}_probability"]) for a in ("dw", "rr", "radio"))
    view = ap.compose(floor, _FEATS, eur_per_stream=0.10, worth={"DW": 40.0})
    assert [r["proba"] for r in view["rows"]] == [None, None, None], (
        "a probability on the calibration floor was shown as a percentage")
    assert view["streams_gap"] and view["budget"] == view["streams_gap"] * 0.10
    assert view["rows"][0]["worth"] == 40.0 and view["rows"][1]["worth"] is None

    strong = {"dw_probability": 0.80, "rr_probability": 0.80, "radio_probability": 0.80}
    shown = ap.compose(strong, _FEATS, eur_per_stream=0.10, worth={})
    assert all(r["proba"] == 0.80 for r in shown["rows"])

    no_cost = ap.compose(floor, _FEATS, eur_per_stream=None, worth={})
    assert no_cost["streams_gap"] and no_cost["budget"] is None

    nothing = ap.compose(None, {}, eur_per_stream=0.10, worth={})
    assert all(r["proba"] is None and r["next"] is None for r in nothing["rows"])
    assert nothing["budget"] is None


def test_an_algo_stream_estimate_is_refused_under_its_minimum():
    """R247 (fiche 43): a cell with fewer triggered songs than MIN_N gives NO number."""
    import importlib.util
    from pathlib import Path
    import pandas as pd
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "export_algo_stream_estimates", root / "machine_learning/export_algo_stream_estimates.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    col = mod.COLUMNS["dw"]
    thr = mod.TARGET_THRESHOLDS["dw"]
    rows = [{"DaysSinceRelease": 10, col: thr + 1 + i} for i in range(mod.MIN_N)]
    rows += [{"DaysSinceRelease": 10, col: thr}]               # at the threshold: not triggered
    rows += [{"DaysSinceRelease": 180, col: thr + 50}]        # one 6-month song only
    d = pd.DataFrame(rows).assign(**{mod.COLUMNS["rr"]: 0, mod.COLUMNS["radio"]: 0})
    est = mod.estimates(d)["dw"]
    assert est["j28"]["n"] == mod.MIN_N and "p50" in est["j28"]
    assert est["m6"] == {"n": 1, "refused": True}
    from src.dashboard.views.trigger_algo._tab_algo_streams import estimates_figure
    fig = estimates_figure({"estimates": {"dw": est}})
    notes = " ".join(a.text.replace("<br>", " ") for a in fig.layout.annotations)
    assert "pas assez de titres" in notes and "(1)" in notes, notes
