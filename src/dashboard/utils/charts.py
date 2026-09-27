"""Shared Plotly chart builders for Meta Ads views.

Type: Utility
Uses: plotly, pandas
Persists in: nothing

Factors the dual-axis Pareto (spend bars + CPR line) reused across the overview
and breakdowns views. Coerces Postgres NUMERIC (Decimal) to float so Plotly/Altair
never mis-type the columns.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def pareto_spend_cpr(df, dim_col: str, title: str, *, top_n: int = 15):
    """Bar (spend) + line (CPR) dual-axis Pareto, sorted by spend desc, top N.

    `df` must expose `dim_col`, `spend`, `results`. CPR = spend/results (None when
    no result → the line gaps, never a fake 0). Returns a go.Figure or None if empty.
    """
    if df is None or df.empty:
        return None
    df = df.copy()
    df['spend'] = pd.to_numeric(df['spend'], errors='coerce').fillna(0.0)
    df['results'] = pd.to_numeric(df['results'], errors='coerce').fillna(0.0)
    df['cpr'] = (df['spend'] / df['results'].where(df['results'] != 0)).astype(float)
    df = df.sort_values('spend', ascending=False).head(top_n)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df[dim_col], y=df['spend'], name='Dépense (€)',
        marker_color='rgba(0, 63, 92, 0.6)', yaxis='y',
    ))
    fig.add_trace(go.Scatter(
        # R146 — ce helper est appelé par `meta_ads_overview` ET `meta_breakdowns` :
        # nommer le clic ICI corrige les deux d'un coup, et tout appelant futur.
        x=df[dim_col], y=df['cpr'], name='CPR (€/clic sortant)', mode='lines+markers',
        line={'color': '#ff6361', 'width': 3}, yaxis='y2',
    ))
    fig.update_layout(
        title=title,
        yaxis={'title': 'Dépense (€)', 'showgrid': False},
        yaxis2={'title': 'CPR (€/clic sortant)', 'overlaying': 'y', 'side': 'right',
                'showgrid': False},
        showlegend=False, height=400, margin={'t': 50},
    )
    return fig


# ── R243 — THE drawing door (owner, 2026-09-27) ──────────────────────────────────────
#
# « mettre des légendes sur tous les graphes » (he could not tell what CPR meant),
# « toujours tracer en Pareto », « des couleurs qui permettent la distinction ». Every
# figure of the app goes through `plotly_chart` below; `tests/test_every_chart_goes_
# through_the_door.py` refuses a `.plotly_chart(` anywhere else in src/.
#
# What the door does, and deliberately does NOT do (code-critic, R243):
#   • legend — only when ≥ 2 traces would show one, and never over a legend the figure
#     already set (a per-trace `showlegend=False` counts: an empty legend band is chrome);
#   • glossary — the jargon found in titles, axes and trace names is defined in one line
#     under the chart, from ONE dictionary;
#   • Pareto — OPT-IN per site (`pareto=True`): auto-detection would re-sort each panel of
#     a shared-axis figure on its own and break the row alignment (meta_creatives
#     ranking), or shuffle an ordinal axis (age ranges). Ordering is presentation, not a
#     metric definition, so it does not belong in the gold layer either.

GLOSSARY: dict[str, tuple[str, str]] = {
    # term: (i18n key, French definition) — matched as a whole word, case-sensitive.
    "CPR": ("charts.gloss.cpr", "CPR = coût par résultat : la dépense divisée par le nombre de résultats (ici, les clics vers les plateformes)"),
    "CTR": ("charts.gloss.ctr", "CTR = taux de clic : clics ÷ impressions, en %"),
    "CPM": ("charts.gloss.cpm", "CPM = coût pour 1 000 impressions"),
    "CPC": ("charts.gloss.cpc", "CPC = coût par clic"),
    "DW": ("charts.gloss.dw", "DW = Discover Weekly"),
    "RR": ("charts.gloss.rr", "RR = Release Radar"),
    "PI": ("charts.gloss.pi", "PI = indice de popularité Spotify (0 à 100)"),
    "LTV": ("charts.gloss.ltv", "LTV = ce qu'un abonné rapporte sur toute sa durée d'abonnement"),
    "MRR": ("charts.gloss.mrr", "MRR = revenu mensuel récurrent des abonnements"),
    "SHAP": ("charts.gloss.shap", "SHAP = la part de chaque variable dans la prédiction du modèle"),
}


def _texts(fig) -> list[str]:
    """Every string a reader sees on the figure: title, axis titles, trace names."""
    lay = fig.layout
    out = [str(getattr(lay.title, "text", "") or "")]
    for name in dir(lay):
        if name.startswith(("xaxis", "yaxis")):
            ax = getattr(lay, name, None)
            title = getattr(getattr(ax, "title", None), "text", None)
            if title:
                out.append(str(title))
    for ann in lay.annotations or ():
        out.append(str(ann.text or ""))
    out += [str(tr.name or "") for tr in fig.data]
    return out


def jargon(fig) -> list[str]:
    """The glossary terms the figure shows, in dictionary order. Pure."""
    import re
    text = " ".join(_texts(fig))
    return [k for k in GLOSSARY if re.search(rf"(?<![A-Za-z]){k}(?![A-Za-z])", text)]


def _legend_would_show(fig) -> int:
    return sum(1 for tr in fig.data if tr.name and tr.showlegend is not False)


def apply_defaults(fig, *, pareto: bool | None = None):
    """The door's changes to the figure itself — legend, palette, Pareto. Pure on `fig`."""
    from src.dashboard.utils.platform_colors import DISTINCT
    lay = fig.layout
    if lay.showlegend is None and lay.legend.orientation is None and _legend_would_show(fig) >= 2:
        fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="top",
                                                       y=-0.18, xanchor="left", x=0))
    if not lay.colorway and not any(_has_colour(tr) for tr in fig.data):
        fig.update_layout(colorway=list(DISTINCT))
    if pareto:
        for tr in fig.data:
            if tr.type == "bar":
                horiz = tr.orientation == "h"
                axis = "yaxis" if horiz else "xaxis"
                ref = (tr.yaxis if horiz else tr.xaxis) or axis[0]
                key = axis + ref[1:]
                fig.layout[key].categoryorder = "total ascending" if horiz else "total descending"
    return fig


def _has_colour(tr) -> bool:
    marker = getattr(tr, "marker", None)
    line = getattr(tr, "line", None)
    return bool((marker is not None and marker.color is not None)
                or (line is not None and line.color is not None))


def plotly_chart(fig, *, container=None, pareto: bool | None = None, glossary: bool = True,
                 **kwargs):
    """Draw `fig` — THE way every chart of the app reaches the screen (R243)."""
    import streamlit as st

    from src.dashboard.utils.i18n import t
    target = container if container is not None else st
    if fig is not None and hasattr(fig, "layout"):
        apply_defaults(fig, pareto=pareto)
    out = target.plotly_chart(fig, **kwargs)
    if glossary and fig is not None and hasattr(fig, "layout"):
        terms = jargon(fig)
        if terms:
            target.caption(" · ".join(t(GLOSSARY[k][0], GLOSSARY[k][1]) for k in terms))
    return out
