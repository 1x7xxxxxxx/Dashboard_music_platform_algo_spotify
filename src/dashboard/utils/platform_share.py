"""The home pie — each platform's share of the total streams shown above it (R371).

Type: Utility
Uses: plotly, platform_colors
Depends on: nothing from the database — it reads the `totals` dict already computed
Triggers: src/dashboard/views/home_tiles.py (render_tiles)
Persists in: nothing

The pie draws THE SAME dict the big total sums (`platform_totals`, which reads
`v_platform_totals` for « depuis le début » and the measured deltas for a bounded
period). It never sums a cumulative counter on its own: a second calculation would be
a second total, and the home page already paid for three totals on three pages.
So the sum of its slices equals `combined_total(totals)` by construction — an absent
platform (`None`) or a zero is left out, never drawn as a zero-width slice.
"""
from __future__ import annotations

import plotly.graph_objects as go

from src.dashboard.utils.platform_colors import is_dark, platform_color

#: Draw order of the slices — the order the platform tiles below are declared in.
PIE_PLATFORMS = (
    ("spotify", "Spotify"),
    ("youtube", "YouTube"),
    ("apple", "Apple Music"),
    ("soundcloud", "SoundCloud"),
)


def platform_share_figure(totals: dict) -> go.Figure | None:
    """A pie of the measured platforms, values on the slices; `None` under 2 slices.

    One slice is not a share: a 100 % disc says nothing the total does not.
    """
    parts = [(key, label, (totals or {}).get(key)) for key, label in PIE_PLATFORMS]
    parts = [(k, lab, v) for k, lab, v in parts if v]
    if len(parts) < 2:
        return None
    dark = is_dark()
    fig = go.Figure(go.Pie(
        labels=[lab for _k, lab, _v in parts],
        values=[v for _k, _lab, v in parts],
        marker=dict(colors=[platform_color(k, dark=dark) for k, _lab, _v in parts]),
        texttemplate="%{label}<br>%{value:,.0f} · %{percent:.1%}",
        # Horizontal, and OUTSIDE when a slice is too thin: looked at the 2026-10-05
        # render — rotated text, and a 4.6 % slice whose label was unreadable.
        textposition="auto",
        insidetextorientation="horizontal",
        # R421 — an outside label is pushed past a fixed frame: « l'étiquette de
        # SoundCloud en bas est crop » (2026-10-06). automargin grows the frame to it.
        automargin=True,
        sort=False,
        hole=0.35,
    ))
    fig.update_layout(height=340, margin=dict(l=40, r=40, t=40, b=40), showlegend=False,
                      separators=", ")
    return fig
