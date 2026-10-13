"""The engagement breakdown as a grid — one cell per (value, action), its count written (R558).

Type: Utility
Uses: pandas, plotly, src.dashboard.utils.formats, src.dashboard.utils.platform_colors
Triggers: views/meta_breakdowns.py (`_render_engagement`)
Persists in: nothing

Owner's note of 2026-10-13, fiche 33: « tu me mets en légende réaction, commentaire,
enregistrement, partage, clic sur lien, mais je vois uniquement les réactions et les clics
sur lien ». Nothing was lost: measured the same day, the account carried 12 248 reactions
against 39 comments and 8 shares. On ONE stacked axis the small actions are a pixel wide.

Each column is now scaled to ITS OWN maximum, so the age that comments most is as dark as
the age that reacts most, and the number is written in the cell — a colour never stands
alone for a count.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils.formats import num
from src.dashboard.utils.platform_colors import platform_color

_EMPTY_INK = "#f4f4f4"


def column_shade(values: pd.DataFrame) -> pd.DataFrame:
    """Each column divided by its own maximum, 0 where the column is all zero. Pure."""
    top = values.max()
    return values.div(top.where(top > 0), axis=1).astype(float).fillna(0.0)


#: The cell's look, shared so the view builds the Heatmap itself: the gold-coverage map
#: follows a figure's data through the function that READS it, and a helper that took
#: the frame added one hop too many (measured on R558: « indéterminée », motif profondeur).
HEATMAP_STYLE = dict(
    texttemplate="%{text}", colorscale=[[0, _EMPTY_INK], [1, platform_color("meta")]],
    showscale=False, xgap=2, ygap=2, zmin=0, zmax=1,
    hovertemplate="%{y} · %{x} : %{customdata:,.0f}<extra></extra>")


def cell_text(values: pd.DataFrame) -> list[list[str]]:
    """The count of every cell, formatted — a colour never stands alone for a count."""
    return [[num(float(v), 0) for v in row] for row in values.astype(float).values]


def dress(fig: go.Figure, title: str, rows: int) -> None:
    """Axes and size of one panel: actions on top, the biggest value first."""
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig.update_xaxes(side="top")
    fig.update_layout(title=title, height=90 + 34 * rows, margin={"t": 80, "r": 10})


def totals_line(base: pd.DataFrame, labels: dict[str, str]) -> str:
    """« 12 248 Réactions · 39 Commentaires · … » — the account's totals, one breakdown's rows."""
    return " · ".join(f"**{num(float(pd.to_numeric(base[c], errors='coerce').sum()), 0)}** {lbl}"
                      for c, lbl in labels.items())
