"""R601 (owner, 2026-10-15) — « Release Radar : la courbe ne retombe pas après le 1er mois ».

Type: Test
Uses: machine_learning/export_algo_stream_estimates.py,
      src/dashboard/views/trigger_algo/_tab_algo_streams.py

Cause, measured on data_anon.csv: of the 244 rows older than 90 days, none carries a single
Release Radar stream (weekly playlist, it ends). The export kept only TRIGGERED rows per age,
so an age where no song triggers came out `refused` — « pas assez de titres » — and the
curve stopped at J+28. An age bucket of ≥ MIN_N songs all at zero is a measured zero.
"""
import importlib.util
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

_SPEC = importlib.util.spec_from_file_location(
    "export_estimates", Path("machine_learning/export_algo_stream_estimates.py"))
exp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(exp)


def _frame() -> pd.DataFrame:
    young = [{"DaysSinceRelease": 20, "ReleaseRadarStreamsLast28Days": 500.0}] * 12
    old = [{"DaysSinceRelease": 180, "ReleaseRadarStreamsLast28Days": 0.0}] * 12
    thin = [{"DaysSinceRelease": 365, "ReleaseRadarStreamsLast28Days": 0.0}] * 3
    d = pd.DataFrame(young + old + thin)
    d["DiscoverWeeklyStreamsLast28Days"] = d["RadioStreamsLast28Days"] = 0.0
    return d


def test_an_age_where_every_song_is_at_zero_is_a_zero_not_a_refusal():
    rr = exp.estimates(_frame())["rr"]
    assert rr["j28"]["p50"] == 500.0
    assert rr["m6"] == {"p25": 0.0, "p50": 0.0, "p75": 0.0, "n": 12, "zero": True}
    assert rr["y1"] == {"n": 0, "refused": True}, "3 songs prove nothing: still refused"


def test_some_streams_left_is_not_a_zero():
    d = _frame()
    d.loc[d["DaysSinceRelease"] == 180, "ReleaseRadarStreamsLast28Days"] = [5.0] + [0.0] * 11
    assert exp.estimates(d)["rr"]["m6"].get("refused") is True


def test_the_cohort_line_lands_on_the_zero_and_says_so():
    from src.dashboard.views.trigger_algo import _tab_algo_streams as ests
    fig = go.Figure()
    ests.cohort_traces(fig, exp.estimates(_frame())["rr"], "#cc0000", row=None, col=None,
                       first=True)
    line = [tr for tr in fig.data if tr.mode == "lines+markers+text"][0]
    assert list(line.y) == [500.0, 0.0], "the fall is drawn"
    assert any("s'éteint" in (a.text or "") for a in fig.layout.annotations)
