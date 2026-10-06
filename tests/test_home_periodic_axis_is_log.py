"""R427 — Home's non-cumulative chart uses a log Y axis; other pages and Cumulé keep linear.

Type: Test
Uses: src/dashboard/utils/platform_chart.py (render_platform_chart, log_periodic)
Persists in: nothing

The owner, 2026-10-06: « quand je décoche le cumulé, je n'ai pas les data pour SoundCloud
et YouTube ». Measured on prod: YouTube +25..49 and SoundCloud +20..37 a month against
Spotify +650..700 — drawn, but flattened at zero on a linear axis.
"""
from __future__ import annotations

import datetime as dt
import json
from unittest import mock

import pytest

from src.dashboard.utils import platform_chart


def _series() -> dict:
    day0 = dt.date(2026, 7, 1)
    days = [day0 + dt.timedelta(d) for d in range(60)]
    return {"spotify": [(d, 25) for d in days],
            "youtube": [(d, 1) for d in days],
            "soundcloud": [(d, 1) for d in days]}


def _layout(**kw) -> dict:
    figs = []
    with mock.patch.object(platform_chart.charts, "plotly_chart",
                           side_effect=lambda fig, **_: figs.append(fig)):
        assert platform_chart.render_platform_chart(_series(), notes=False, **kw)
    spec = json.loads(figs[0].to_json())
    return {"axis": spec["layout"].get("yaxis", {}).get("type"),
            "stacked": any(tr.get("stackgroup") for tr in spec["data"])}


@pytest.mark.parametrize("mode, log, want", [
    ("absolute", True, "log"),          # Home, Cumulé off
    ("cumulative", True, None),         # Home, Cumulé on: levels stay linear
    ("absolute", False, None),          # any other page
])
def test_only_homes_non_cumulative_chart_is_log(mode, log, want) -> None:
    got = _layout(mode=mode, log_periodic=log)
    assert got["axis"] == want
    # Stacked on a log axis, the small platforms would ride on Spotify's band.
    assert not (want == "log" and got["stacked"])
