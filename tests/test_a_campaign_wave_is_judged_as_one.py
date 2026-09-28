"""Overlapping campaigns are judged together, as a WAVE, with the listener verdict's refusals (R291).

Measured 2026-09-28 on artist 1: judged one by one, 21 of 21 campaigns were « non concluant »,
almost all because another campaign spent at the same time. `meta_impact.waves` groups them by
the verdict's own overlap rule (the 28-day baseline), so a wave never overlaps another's window.

Does not cover: the causal question — a wave often coincides with a release; the figure's
caption says it is an association.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.dashboard.utils import meta_impact as mi

D = dt.date


def _c(name, start, end, spend=100.0):
    return mi.Campaign("act", name, start, end, spend)


def test_overlapping_or_close_campaigns_form_one_wave_and_far_ones_do_not():
    a = _c("A", D(2024, 1, 1), D(2024, 1, 20))
    b = _c("B", D(2024, 1, 10), D(2024, 2, 1))         # overlaps A
    c = _c("C", D(2024, 2, 20), D(2024, 3, 1))         # 19 days after B: inside the baseline
    far = _c("D", D(2024, 6, 1), D(2024, 6, 20))
    got = mi.waves([far, c, b, a])
    assert [names for _, names in got] == [["A", "B", "C"], ["D"]]
    wave, _ = got[0]
    assert (wave.start, wave.end, wave.spend) == (D(2024, 1, 1), D(2024, 3, 1), 300.0)


def test_no_wave_overlaps_the_window_of_another():
    got = [w for w, _ in mi.waves([_c("A", D(2024, 1, 1), D(2024, 1, 20)),
                                   _c("B", D(2024, 3, 1), D(2024, 3, 10))])]
    today = D(2025, 1, 1)
    days = pd.date_range("2023-11-01", "2024-04-30", freq="D")
    series = pd.Series(100.0, index=days)
    for w in got:
        assert "impossible de les séparer" not in mi.verdict_for(w, got, series, today).text


def test_the_last_campaign_verdict_is_unchanged_by_the_refactor():
    days = pd.date_range("2024-01-01", "2024-03-31", freq="D")
    series = pd.Series(100.0, index=days)
    series[series.index >= "2024-03-01"] = 400.0
    camp = [_c("A", D(2024, 3, 1), D(2024, 3, 20), 300.0)]
    v = mi.verdict(series, camp, D(2024, 4, 30))
    assert v.conclusive and v.lift_per_day == 300.0 and "auditeurs-jour" in v.text
    w = mi.verdict_for(camp[0], camp, series, D(2024, 4, 30), mi.STREAMS)
    assert w.lift_per_day == 300.0 and "écoutes" in w.text
