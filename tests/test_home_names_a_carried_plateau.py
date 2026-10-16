"""R627 — Home writes ONE line under its figure: a counter's plateau is carried, not measured.

Type: Test
Uses: src/dashboard/utils/platform_chart.py (render_platform_chart, carried_caption)
Persists in: nothing

The owner, 2026-10-16, approved this single exception to R421 (« retire-moi tout le
texte sous le graphique »). The PDF already carried it (R614).

guard_scope: the caption's presence when a lifetime counter is drawn, and its absence
when none is (no counter series, or a daily non-cumulative step where nothing is
carried). NOT covered: its wording (i18n catalog), the other notes `notes=False` hides.
"""
from __future__ import annotations

import datetime as dt
from unittest import mock

import pytest

from src.dashboard.utils import platform_chart

_DAY0 = dt.date(2026, 7, 1)
_DAYS = [_DAY0 + dt.timedelta(d) for d in range(60)]


def _captions(cumulative: dict | None, **kw) -> list[str]:
    series = {"spotify": [(d, 25) for d in _DAYS], "youtube": [(d, 1) for d in _DAYS]}
    out: list[str] = []
    with mock.patch.object(platform_chart.charts, "plotly_chart"), \
            mock.patch.object(platform_chart.st, "caption", side_effect=out.append):
        assert platform_chart.render_platform_chart(
            series, notes=False, carried_caption=True, cumulative=cumulative,
            since=_DAYS[0], until=_DAYS[-1], **kw)
    return out


_COUNTER = {"youtube": [(_DAYS[0], 100), (_DAYS[30], 140)]}


def test_a_drawn_counter_is_named_as_carried() -> None:
    lines = _captions(_COUNTER, mode="cumulative")
    assert len(lines) == 1 and "YouTube" in lines[0]


@pytest.mark.parametrize("cumulative, kw", [
    (None, {"mode": "cumulative"}),                      # no counter at all
    (_COUNTER, {"mode": "absolute", "step": "day"}),     # daily growth: nothing carried
])
def test_no_carried_counter_no_line(cumulative, kw) -> None:
    assert _captions(cumulative, **kw) == []


def test_other_callers_get_no_line_by_default() -> None:
    out: list[str] = []
    with mock.patch.object(platform_chart.charts, "plotly_chart"), \
            mock.patch.object(platform_chart.st, "caption", side_effect=out.append):
        platform_chart.render_platform_chart(
            {"youtube": [(d, 1) for d in _DAYS]}, notes=False, cumulative=_COUNTER,
            since=_DAYS[0], until=_DAYS[-1])
    assert out == []


def test_the_line_has_an_english_translation() -> None:
    from src.dashboard.utils.i18n_catalog import home
    assert "{names}" in home.EN["platform_chart.carried_level"]
