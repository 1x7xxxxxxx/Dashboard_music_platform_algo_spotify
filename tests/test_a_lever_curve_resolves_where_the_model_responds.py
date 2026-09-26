"""A lever curve must have its resolution where the model responds, and the Pareto
must price a lever from the model, not from that curve.

Type: Utility
Uses: src.utils.ml_inference (local_sensitivity, lever_probability, load_model,
      _calibrate), src.dashboard.views.trigger_algo._pareto (_delta_proba),
      src.dashboard.utils.algo_knowledge (ALGO_FEATURE_ZONES)
Depends on: the committed v3 model artefacts under machine_learning/models/v3 (no DB)
Triggers: nothing
Persists in: nothing

The defect (measured 2026-09-26 on spotify_etl_review, artist 1, latest predictions):
`local_sensitivity` bounded a `_log` lever in MODEL space (expm1(12.308) = 221 460
streams for StreamsLast7Days) and then sampled it LINEARLY in human units — a step of
9 227 streams. Point 0 sat at x=0, every other point at x >= 9 227, so the whole
0..10k response, the 2 000 target included, was drawn as one straight segment.
Read at the target by interpolation: DW 9.6 % for an exact 14.1 %, RADIO 27.8 % for
an exact 84.8 %. The Pareto priced the lever by interpolating that curve, so it
showed +2.3 pts DW instead of +6.8 and +16 RADIO instead of +73.

This is a TEST, not a catalogued class: one producer and two consumers of the same
artefact, no recorded recurrence, no P1 — the admission ticket of rule 15 does not
hold.

The input is ONE real review-DB song's feature vector, embedded as a literal so the
input does not depend on the code under test.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("xgboost")

from src.dashboard.utils.algo_knowledge import ALGO_FEATURE_ZONES  # noqa: E402
from src.dashboard.views.trigger_algo import _pareto  # noqa: E402
from src.utils import ml_inference as mi  # noqa: E402

_FEATS = {
    "DaysSinceRelease": 924.0, "Velocity_Streams": 0.0, "ReleasePhaseEarly": 0.0,
    "SavesLast28Days_adj": 0.0, "StreamsLast7Days_log": 0.0,
    "ReleaseConsistencyNum": 3.0, "NonAlgoStreams28Days_log": 3.1780538303479453,
    "PlaylistAddsLast28Days_adj": 7.0,
    "CurrentSpotifyFollowers_log": 6.5250296578434615,
    "ListenersStreamRatio28Days_adj": 1.2195121951219512,
    "HowManySongsDoYouHaveInRadioRightNow": 0.0,
    "HowManySongsHasThisArtistEverReleased": 11.0,
    "IsThisSongOptedIntoSpotifyDiscoveryMode": 0.0,
    "radio_known": True, "nonalgo_known": True, "discovery_mode_known": True,
}

#: Tolerance for reading the curve at a target it was NOT told about. Measured with
#: the model-space grid: worst case RADIO StreamsLast7Days, 82.9 % read for 84.8 %
#: exact (1.9 pts). The linear grid missed by 4.5 pts (DW) and 57 pts (RADIO).
_CURVE_TOL = 0.03

_LOG_LEVERS = [
    (algo, spec["json_key"], float(spec["target"]))
    for algo, zones in ALGO_FEATURE_ZONES.items()
    for spec in zones.values()
    if (spec.get("json_key") or "").endswith("_log") and spec.get("target")
]


def _direct(algo: str, feature: str, x_human: float) -> float:
    """The calibrated probability at `x_human`, computed here without the curve."""
    key = {"DW": "dw", "RR": "rr", "RADIO": "radio"}[algo]
    row = dict(_FEATS)
    row[feature] = float(np.log1p(x_human))
    X = pd.DataFrame([[float(row.get(c, 0.0)) for c in mi.FEATURE_COLUMNS]],
                     columns=mi.FEATURE_COLUMNS)
    clf = mi.load_model(f"{key}_classifier")
    return mi._calibrate(key, float(clf.predict_proba(X)[0, 1]))


def _ids(p):
    return f"{p[0]}-{p[1]}"


def test_there_are_log_levers_with_a_target():
    """Anti-vacuity: the parametrised tests below must have something to check."""
    assert len(_LOG_LEVERS) >= 4, _LOG_LEVERS


def test_the_model_really_responds_below_the_first_linear_step():
    """Anti-vacuity: a flat model would let every curve pass. Measured +6.8 pts."""
    gain = _direct("DW", "StreamsLast7Days_log", 2000.0) - _direct(
        "DW", "StreamsLast7Days_log", 0.0)
    assert gain >= 0.03, f"DW 0 -> 2000 streams moves only {gain * 100:.1f} pts"


@pytest.mark.parametrize("lever", _LOG_LEVERS, ids=_ids)
def test_the_curve_reads_the_target_without_being_told_it(lever):
    algo, feature, target = lever
    res = mi.local_sensitivity(algo, feature, _FEATS)
    assert res is not None
    read = float(np.interp(target, res["x_human"], res["probs"]))
    exact = _direct(algo, feature, target)
    assert abs(read - exact) <= _CURVE_TOL, (
        f"{algo}/{feature}: the curve reads {read * 100:.1f} % at {target:,.0f}, "
        f"the model gives {exact * 100:.1f} %. A `_log` lever sampled linearly in "
        "human units puts one grid step (~9 227 streams) over the whole response."
    )


@pytest.mark.parametrize("lever", _LOG_LEVERS, ids=_ids)
def test_the_grid_is_dense_where_the_target_lives(lever):
    algo, feature, target = lever
    res = mi.local_sensitivity(algo, feature, _FEATS)
    below = sum(1 for x in res["x_human"] if x <= 10 * target)
    assert below >= 5, (
        f"{algo}/{feature}: only {below} grid points at or below 10 x the target "
        f"({10 * target:,.0f}) — the curve cannot show where the model responds."
    )


@pytest.mark.parametrize("lever", _LOG_LEVERS, ids=_ids)
def test_current_and_target_are_exact_grid_points(lever):
    algo, feature, target = lever
    res = mi.local_sensitivity(algo, feature, _FEATS, targets=(target,))
    xs, ps = res["x_human"], res["probs"]
    cur = res["current"]
    assert float(np.interp(target, xs, ps)) == pytest.approx(
        _direct(algo, feature, target), abs=1e-6)
    assert float(np.interp(cur, xs, ps)) == pytest.approx(
        _direct(algo, feature, cur), abs=1e-6)


@pytest.mark.parametrize("lever", _LOG_LEVERS, ids=_ids)
def test_the_pareto_prices_a_lever_from_the_model(lever):
    algo, feature, target = lever
    cur = float(np.expm1(_FEATS[feature]))
    expected = max(0.0, _direct(algo, feature, target) - _direct(algo, feature, cur))
    got = _pareto._delta_proba(algo, feature, _FEATS, cur, target)
    assert got == pytest.approx(expected, abs=1e-6), (
        f"{algo}/{feature}: the Pareto prices {cur:,.0f} -> {target:,.0f} at "
        f"{(got or 0) * 100:+.2f} pts, the model says {expected * 100:+.2f}. "
        "A lever's euro value must come from two model calls, not a display curve."
    )
