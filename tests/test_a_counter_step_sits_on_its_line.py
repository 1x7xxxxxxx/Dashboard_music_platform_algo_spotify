"""A counter's first reading is marked where its step is DRAWN, in its own colour (R288).

Owner, 2026-09-28 (fiche 1): « le deuxième pointillé, il est pas sur YouTube ». Two grey
dotted lines, labels stacked at the top: the SoundCloud line was read as a misplaced YouTube
one, and the YouTube area rose in a slope that started before its line (interpolated from the
empty point before its first reading). Now its line sits on the first plotted x, in the
platform's colour. A `shape="hv"` step was tried and refused on the render: stacked on a
linear trace, it painted wedges over the whole history.

Does not cover: the other modes (share, per-period), where no arrival is marked.
"""
from __future__ import annotations

import datetime as dt

import plotly.graph_objects as go

from src.dashboard.utils.platform_chart_notes import first_plotted, mark_counter_arrivals

D = [dt.date(2025, 10, 1), dt.date(2025, 11, 1), dt.date(2025, 12, 1)]


def test_the_line_moves_to_the_first_plotted_bucket():
    arrivals = [(dt.date(2025, 11, 17), "youtube", 118_032)]
    aligned = {"youtube": [None, 118_032, 118_500]}
    assert first_plotted(arrivals, aligned, D) == [(D[1], "youtube", 118_032)]


def test_each_line_takes_its_platforms_colour():
    fig = go.Figure()
    mark_counter_arrivals(fig, [(D[1], "youtube", 1), (D[2], "soundcloud", 2)],
                          {"youtube": "YouTube", "soundcloud": "SoundCloud"}, "#999",
                          {"youtube": "#bd354b", "soundcloud": "#e0631b"})
    assert [s.line.color for s in fig.layout.shapes] == ["#bd354b", "#e0631b"]
    assert [a.font.color for a in fig.layout.annotations] == ["#bd354b", "#e0631b"]
