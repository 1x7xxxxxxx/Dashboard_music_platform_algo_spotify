"""Cumulative curves aligned on an age axis, each labelled at its last point.

Type: Utility
Uses: plotly, utils.formats.num
Depends on: —
Persists in: —

One drawing rule for every « compare at equal age » figure: the Spotify releases
(« Mes sorties, à âge égal ») and the SoundCloud catalogue (R385). It was written
inline in the Spotify view; the owner asked SoundCloud to reuse it, so it lives here
once instead of being copied.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils.formats import num


def age_aligned_traces(df: pd.DataFrame, *, x: str, y: str, series: str,
                       colour: dict, markers: bool = False) -> list[go.Scatter]:
    """One line per `series` value, in the frame's order, with its value at the end.

    THE VALUE LABEL IS ON THE LAST POINT, AND NOWHERE ELSE: the end of the common
    horizon is the only abscissa where two curves compare, so the only one where a
    number decides something. Labelling every point would print hundreds of numbers
    on top of each other — the opposite of what one comes to read.
    """
    traces = []
    for name, grp in df.groupby(series, sort=False):
        labels = [""] * len(grp)
        if labels:
            labels[-1] = num(int(grp[y].iloc[-1]), 0)
        traces.append(go.Scatter(
            x=grp[x], y=grp[y], name=str(name), legendgroup=str(name),
            mode="lines+markers+text" if markers else "lines+text",
            line=dict(width=2.5, color=colour.get(name, "#888")),
            text=labels, textposition="top left" if markers else "middle left",
            textfont=dict(size=13), cliponaxis=False))
    return traces
