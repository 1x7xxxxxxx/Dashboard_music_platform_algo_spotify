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



def spend_ring(df, dim_col: str, title: str):
    """A ring of the SPEND split by `dim_col`, each slice labelled with its € and its CPR.

    R245 (fiche 23, owner 2026-09-27 : « changer le graphe en rond pour la lisibilité »).
    CPR = spend / results, « — » when a slice has no result (never a fake 0 €). Returns a
    go.Figure, or None when there is nothing spent."""
    if df is None or df.empty:
        return None
    d = df.copy()
    d['spend'] = pd.to_numeric(d['spend'], errors='coerce').fillna(0.0)
    d['results'] = pd.to_numeric(d['results'], errors='coerce').fillna(0.0)
    d = d[d['spend'] > 0].sort_values('spend', ascending=False)
    if d.empty:
        return None
    cpr = d['spend'] / d['results'].where(d['results'] > 0)
    eur = lambda v: f"{v:,.0f}".replace(",", " ")   # noqa: E731
    text = [f"{eur(sp)} € · CPR {c:.2f} €".replace(".", ",") if c == c else f"{eur(sp)} € · CPR —"
            for sp, c in zip(d['spend'], cpr)]
    fig = go.Figure(go.Pie(
        labels=d[dim_col].astype(str), values=d['spend'], hole=0.55, sort=False,
        text=text, textinfo="label+text", textposition="outside",
        hovertemplate="%{label}<br>%{value:,.0f} € (%{percent})<extra></extra>"))
    fig.update_layout(title=title, height=420, showlegend=False,
                      annotations=[dict(text=f"<b>{eur(d['spend'].sum())} €</b>", showarrow=False,
                                        font=dict(size=16))])
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
    """Does the trace set its own colour? Read defensively: a Pie's marker has `colors`, not
    `color`, and an Indicator has no marker at all — the first door read `marker.color` and
    every page with a ring crashed (hypeddit, 2026-09-27, R245 render)."""
    for part_name in ("marker", "line"):
        part = getattr(tr, part_name, None)
        if part is None:
            continue
        for attr in ("color", "colors"):
            try:
                if getattr(part, attr, None) is not None:
                    return True
            except (AttributeError, ValueError):
                continue
    return False


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


def to_base100(fig, title: str = "") -> tuple:
    """(one-frame figure, series left out): every trace re-expressed as an index — 100 at
    its first POSITIVE value — with its real value in the hover. Pure.

    R244 (fiche 5, « fusionner les deux ») : four measures of four units (streams per day,
    a 0–100 index, saves per month, a subscriber level) cannot share an axis as values;
    they can as a trend, which is the question the figure answers (« does it still move »).
    A series with no positive value has no base: it is named, never drawn at 0."""
    import plotly.graph_objects as go
    out, skipped = go.Figure(), []
    for tr in fig.data:
        ys = list(tr.y) if tr.y is not None else []
        base = next((float(v) for v in ys if v is not None and v == v and float(v) > 0), None)
        if base is None:
            skipped.append(tr.name or "")
            continue
        idx = [None if v is None or v != v else 100.0 * float(v) / base for v in ys]
        colour = (tr.marker.color if tr.type == "bar" else tr.line.color) or None
        out.add_trace(go.Scatter(
            x=tr.x, y=idx, mode="lines", name=tr.name, customdata=ys, connectgaps=False,
            visible=tr.visible,
            line=dict(color=colour, width=2 if tr.type != "bar" else 1.5,
                      dash=None if tr.type != "bar" else "dot"),
            hovertemplate=f"{tr.name} : %{{customdata:,.0f}} (indice %{{y:.0f}})<extra></extra>"))
    out.add_hline(y=100, line_dash="dot", line_color="rgba(128,128,128,0.4)")
    out.update_layout(title=title or None, hovermode="x unified",
                      yaxis_title="Indice (100 = première valeur)")
    # A release peak (×10) flattened every other trend under it (render, 2026-09-27): the
    # axis stops at the bulk of the data and the clipped peak is SAID, never hidden.
    vals = sorted(v for tr in out.data for v in (tr.y or ()) if v is not None)
    if vals:
        top, cap = vals[-1], max(200.0, 1.3 * vals[int(0.95 * (len(vals) - 1))])
        if top > cap:
            out.update_yaxes(range=[0, cap])
            out.add_annotation(xref="paper", yref="paper", x=0.01, y=1, showarrow=False,
                               xanchor="left", yanchor="top", font=dict(size=10),
                               text=f"▲ pic hors échelle : indice {top:,.0f}".replace(",", " "))
    return out, skipped
