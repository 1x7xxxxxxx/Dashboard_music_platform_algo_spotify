"""R241 — a lifetime counter entering the stack is marked, not read as an audience peak.

Owner, 2026-09-27, fiche 1: « corrige le pic ». On « depuis le début », YouTube enters the
home stack at its whole past (+118 k) on its first reading (ADR-024: the platform only
reports a lifetime counter). The figure now marks that day with a dotted line and a label.
"""
import datetime as dt

import plotly.graph_objects as go

from src.dashboard.utils.platform_chart_notes import counter_arrivals, mark_counter_arrivals

D = dt.date


def test_a_counter_starting_inside_the_span_is_an_arrival():
    span = [D(2023, 1, 1) + dt.timedelta(days=i) for i in range(1000)]
    cumulative = {"youtube": [(D(2025, 11, 20), 118361), (D(2025, 12, 1), 118500)],
                  "spotify": [(D(2023, 1, 1), 10)]}
    arr = counter_arrivals(cumulative, ["youtube", "spotify"], span)
    assert arr == [(D(2025, 11, 20), "youtube", 118361)], (
        "only the counter that starts AFTER the span's first day arrives")
    assert counter_arrivals({"youtube": []}, ["youtube"], span) == []


def test_the_arrival_is_drawn_on_the_figure():
    fig = go.Figure()
    mark_counter_arrivals(fig, [(D(2025, 11, 20), "youtube", 118361)],
                          {"youtube": "YouTube"}, "#666")
    texts = [a.text for a in fig.layout.annotations]
    assert any("118 361" in x and "YouTube" in x for x in texts), texts
    assert fig.layout.shapes, "no vertical line marks the arrival"
