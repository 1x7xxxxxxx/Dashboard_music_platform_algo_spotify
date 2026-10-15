"""R570 — the track forecast projects the track's OWN decay, and draws a trigger only where
the estimates measured one.

Type: Test
Uses: src/dashboard/views/trigger_algo/_forecast.py

Owner, 2026-10-15: cumulative streams + revenue from J+7 to 10 years, the « if it
triggers » overlay only at the ages the estimates measure (28 days, 6 months). A
playlist effect extrapolated to 10 years would be a number nothing measured; a past
horizon drawn with a band would present a measure as a guess.
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.views.trigger_algo import _forecast as fc


def _hist(days: int, start: float = 1000.0, b: float = 0.6) -> pd.DataFrame:
    """A power-law decay with a deterministic ±20 % weekly wobble (a perfect fit has no band)."""
    ages = range(0, days)
    return pd.DataFrame({"age": list(ages),
                         "streams": [start * max(a, 1) ** -b * (1.2 if a % 7 < 2 else 0.9)
                                     for a in ages]})


def _est() -> dict:
    cell = {"p25": 100.0, "p50": 300.0, "p75": 900.0, "n": 12}
    return {"estimates": {"dw": {"j28": cell, "m6": cell, "y1": cell},
                          "radio": {"j28": {**cell, "refused": True}, "m6": cell}}}


def test_past_horizons_are_measured_and_future_ones_banded() -> None:
    hist = _hist(60)
    path = fc.cumulative_path(hist, fc.fit_decay(hist))
    assert [p["key"] for p in path] == [k for k, _a, _l in fc.HORIZONS]
    for p in path:
        if p["age"] <= 59:
            assert p["measured"] and p["lo"] == p["value"] == p["hi"], p
        else:
            assert not p["measured"] and p["lo"] <= p["value"] <= p["hi"], p
    ahead = [p for p in path if not p["measured"]]
    assert ahead[-1]["hi"] > ahead[-1]["lo"], "a fitted decay must carry a real band"


def test_overlays_only_at_measured_ages_still_ahead() -> None:
    hist = _hist(60)
    path = fc.cumulative_path(hist, fc.fit_decay(hist))
    ov = fc.algo_overlays(_est(), path, last_age=59, order=("DW", "RADIO"))
    assert {(o["algo"], o["age"]) for o in ov} == {("DW", 182), ("RADIO", 182)}, ov
    assert all(o["age"] in fc.OVERLAY_AGES.values() for o in ov)
    assert all(o["y_lo"] <= o["y"] <= o["y_hi"] for o in ov)
    young = fc.algo_overlays(_est(), fc.cumulative_path(_hist(20), fc.fit_decay(_hist(20))),
                             last_age=19, order=("DW", "RADIO"))
    assert ("RADIO", 28) not in {(o["algo"], o["age"]) for o in young}, "refused estimate drawn"
    assert ("DW", 28) in {(o["algo"], o["age"]) for o in young}


def test_too_few_days_fall_back_to_a_flat_rhythm() -> None:
    short = _hist(fc.MIN_POINTS - 1)
    assert fc.fit_decay(short)["kind"] == "flat"
    assert fc.fit_decay(_hist(fc.MIN_POINTS + 2))["kind"] == "power"
    path = fc.cumulative_path(short, fc.fit_decay(short))
    assert all(p["lo"] == p["value"] == p["hi"] for p in path)


def _series(name: str, hist: pd.DataFrame, rate=None, colour="#444444") -> dict:
    return {"name": name, "path": fc.cumulative_path(hist, fc.fit_decay(hist)),
            "overlays": [], "rate": rate, "colour": colour}


def test_one_axis_and_revenue_only_with_a_rate() -> None:
    hist = _hist(60)
    bare = fc.forecast_figure([_series("A", hist)])
    paid = fc.forecast_figure([_series("A", hist, rate=0.003)])
    assert "yaxis2" not in bare.to_plotly_json()["layout"]
    assert not any("€" in (x or "") for tr in bare.data for x in (tr.text or ()))
    assert any("€" in (x or "") for tr in paid.data for x in (tr.text or ()))


def test_both_titles_share_one_figure_and_the_long_term_has_its_colour() -> None:
    """R584 (owner, 2026-10-15) — reference and comparison on the SAME graph, one colour
    each, and the 5- and 10-year points in a colour of their own."""
    fig = fc.forecast_figure([_series("Ref", _hist(60), colour=fc.TITLE_COLORS[0]),
                              _series("Cmp", _hist(200), colour=fc.TITLE_COLORS[1])])
    lines = [tr for tr in fig.data if tr.mode and "lines" in tr.mode]
    assert {tr.name for tr in lines} == {"Ref", "Cmp"}
    assert {tr.line.color for tr in lines} == set(fc.TITLE_COLORS)
    for tr in lines:
        if tr.line.dash != "dot":
            continue
        far = [c for x, c in zip(tr.x, tr.marker.color) if x >= 1826]
        near = [c for x, c in zip(tr.x, tr.marker.color) if x < 1826]
        assert far and set(far) == {fc.LONG_TERM_COLOR}, tr.name
        assert fc.LONG_TERM_COLOR not in near, tr.name
    assert any(tr.name and "long terme" in tr.name for tr in fig.data), "the colour is named"
