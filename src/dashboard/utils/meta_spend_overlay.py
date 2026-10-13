"""Meta Ads spend drawn as an AREA behind another platform's curve (R558).

Type: Utility
Uses: pandas, plotly, src.dashboard.utils.platform_colors, src.dashboard.utils.i18n
Triggers: views/instagram.py (`_render_community`, the monthly engagement figure)
Persists in: nothing

Owner's Y2 of 2026-10-13, fiches 18 and 19: « intégrer à ce graphique les dépenses Meta
Ads, sur une aire, budget Meta Ads sur tel ou tel jour ». An area, not a line: the spend
is the BACKGROUND the community moves on, and a filled light shape reads as context
where a third line would read as one more series to compare.

The spend is the tenant's gold daily spend (`v_meta_daily`), every ad account summed:
an Instagram account grows from every campaign, not from the one in a filter.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils.i18n import t
from src.dashboard.utils.platform_colors import platform_color

# Two literals, not one template: `tools/dev/gold_coverage.py` reads the view name from
# each query's text. `{win}` is the period window's own BETWEEN fragment.
_Q_SPEND = {
    "day": """
        SELECT day AS x, SUM(spend) AS spend
          FROM v_meta_daily
         WHERE artist_id = %s{win}
         GROUP BY 1 ORDER BY 1
    """,
    "month": """
        SELECT date_trunc('month', day)::date AS x, SUM(spend) AS spend
          FROM v_meta_daily
         WHERE artist_id = %s{win}
         GROUP BY 1 ORDER BY 1
    """,
}


def spend_by(db, artist_id: int, window, grain: str = "day") -> pd.DataFrame:
    """x, spend — the tenant's Meta spend per day or month inside the page's period window."""
    if grain not in _Q_SPEND:
        raise ValueError(f"grain must be one of {sorted(_Q_SPEND)}, got {grain!r}")
    win, params = window.sql_between("day")
    df = db.fetch_df(_Q_SPEND[grain].format(win=win), (artist_id, *params))
    if df is None or df.empty:
        return pd.DataFrame(columns=["x", "spend"])
    df = df.copy()
    df["x"] = pd.to_datetime(df["x"])
    df["spend"] = pd.to_numeric(df["spend"], errors="coerce").fillna(0.0)
    return df[df["spend"] > 0]


def area_trace(spend: pd.DataFrame, **kw) -> go.Scatter | None:
    """The filled area, or None when nothing was spent — never an area at zero."""
    if spend is None or spend.empty or float(spend["spend"].sum()) <= 0:
        return None
    ink = platform_color("meta")
    return go.Scatter(
        x=spend["x"], y=spend["spend"], mode="lines", fill="tozeroy",
        line=dict(color=ink, width=0.5), fillcolor=_alpha(ink, 0.18),
        name=t("meta_spend_overlay.name", "Dépense Meta Ads (€)"),
        hovertemplate=t("meta_spend_overlay.hover", "Dépense Meta : %{y:,.0f} €<extra></extra>"),
        **kw)


def _alpha(hex_colour: str, a: float) -> str:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"
