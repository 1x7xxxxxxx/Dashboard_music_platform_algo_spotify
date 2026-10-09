"""Shared Plotly chart builders for Meta Ads views.

Type: Utility
Uses: plotly, pandas
Persists in: nothing

Factors the dual-axis Pareto (spend bars + CPR line) reused across the overview
and breakdowns views. Coerces Postgres NUMERIC (Decimal) to float so Plotly/Altair
never mis-type the columns.
"""
from __future__ import annotations

import re

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
    if pareto is None:
        pareto = pareto_by_default(fig)
    if pareto:
        for tr in fig.data:
            if tr.type == "bar":
                horiz = tr.orientation == "h"
                axis = "yaxis" if horiz else "xaxis"
                ref = (tr.yaxis if horiz else tr.xaxis) or axis[0]
                key = axis + ref[1:]
                fig.layout[key].categoryorder = "total ascending" if horiz else "total descending"
    _unclip_outside_labels(fig)
    return fig


_LABELLED = ("bar", "waterfall", "funnel")
_LABEL_HEADROOM = 1.15


def _unclip_outside_labels(fig) -> None:
    """R474 — a label drawn outside its bar must not be cut by the plot edge.

    Apple Music showed 686 as « 68 »: the default `cliponaxis=True` clips the text at the
    axis, and Plotly's autorange leaves no room for it. Unclip every outside/auto label, and
    give the value axis headroom when the figure set no range and every value is ≥ 0."""
    axes: dict[str, list] = {}
    for tr in fig.data:
        if tr.type not in _LABELLED or tr.textposition not in ("outside", "auto"):
            continue
        if tr.cliponaxis is None:
            tr.cliponaxis = False
        if tr.type == "bar" and tr.textposition == "outside":
            horiz = tr.orientation == "h"
            ref = (tr.xaxis if horiz else tr.yaxis) or "x"
            axes.setdefault(("xaxis" if horiz else "yaxis") + ref[1:], [])
    for tr in fig.data:             # every trace on a padded axis counts, labelled or not
        if not hasattr(tr, "yaxis"):
            continue                # a Pie or an Indicator has no axis
        horiz = tr.type == "bar" and tr.orientation == "h"
        key = ("xaxis" if horiz else "yaxis") + (((tr.xaxis if horiz else tr.yaxis) or "x")[1:])
        if key in axes:
            axes[key].append(tr)
    for key, traces in axes.items():
        top = _value_top(traces, stacked=fig.layout.barmode in ("stack", "relative"))
        axis = fig.layout[key]
        if top and axis.range is None and axis.type in (None, "linear", "-"):
            axis.range = [0, top * _LABEL_HEADROOM]


def _value_top(traces, *, stacked: bool) -> float | None:
    """The highest bar end on one axis — None when a trace is not a plain ≥ 0 bar. Pure."""
    ends: dict = {}
    for tr in traces:
        if tr.type != "bar":
            return None
        horiz = tr.orientation == "h"
        vals, cats = (tr.x, tr.y) if horiz else (tr.y, tr.x)
        vals = list(vals) if vals is not None else []
        cats = list(cats) if cats is not None else list(range(len(vals)))
        for cat, v in zip(cats, vals):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return None
            if v != v or v < 0:
                return None
            ends[cat] = ends.get(cat, 0.0) + v if stacked else max(ends.get(cat, 0.0), v)
    return max(ends.values(), default=0.0) or None


# R260 (fiches 28, 29, 33 : « toujours tracer en Pareto ») — Pareto is the DEFAULT for bars
# over NOMINAL categories (campaigns, countries, creatives, tracks). An order that carries a
# meaning is never reordered: dates, numbers and ranges (« 7 jours », « 18-24 »), months and
# weekdays, a funnel's stages, or an order the figure already set. `pareto=False` opts out.
_ORDINAL = re.compile(
    r"^\s*[<>≤≥~+-]?\s*\d|\b(?:semaines?|weeks?|mois|months?|jours?|days?|ans?|years?|"
    r"q[1-4]|janv|févr|mars|avr|mai|juin|juil|août|sept|oct|nov|déc|jan|feb|mar|apr|may|"
    r"jun|jul|aug|sep|dec|lun|mar|mer|jeu|ven|sam|dim|mon|tue|wed|thu|fri|sat|sun)\b",
    re.IGNORECASE)
_FUNNEL = re.compile(r"funnel|entonnoir|étape|stage", re.IGNORECASE)


def nominal_categories(values) -> bool:
    """True when every category is a label with no order of its own. Pure."""
    vals = [v for v in (values if values is not None else []) if v is not None]
    if len(set(map(str, vals))) < 3 or not all(isinstance(v, str) for v in vals):
        return False
    return not any(_ORDINAL.search(v) for v in vals)


def pareto_by_default(fig) -> bool:
    """Should the door sort this figure's bars by total? Pure on `fig`."""
    bars = [tr for tr in fig.data if tr.type == "bar"]
    if not bars or len(bars) != len(fig.data):
        return False
    texts = " ".join(str(x) for x in [fig.layout.title.text, *(tr.name for tr in bars)] if x)
    if _FUNNEL.search(texts):
        return False
    for tr in bars:
        horiz = tr.orientation == "h"
        axis = ("yaxis" if horiz else "xaxis") + (((tr.yaxis if horiz else tr.xaxis) or "x")[1:])
        lay = fig.layout[axis]
        if lay.categoryorder not in (None, "trace") or lay.categoryarray is not None:
            return False
        if not nominal_categories(tr.y if horiz else tr.x):
            return False
    return True


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


def decision_line(key: str | None) -> str | None:
    """« 🎯 … » — what the chart at `key` lets the artist decide in managing marketing
    campaigns, in the current language (R314). None when the key has no line. Pure but for
    the language read from the session."""
    if not key:
        return None
    from src.dashboard.content.chart_decisions import DECISIONS
    from src.dashboard.utils.i18n import get_lang
    pair = DECISIONS.get(key.removeprefix("src/dashboard/"))
    if pair is None:
        return None
    return "🎯 " + (pair[1] if get_lang() == "en" else pair[0])


def _say_the_decision(target, decision_key: str | None) -> None:
    from src.dashboard.utils.chart_key import caller_key
    line = decision_line(decision_key or caller_key(depth=3))
    if line:
        target.caption(line)


def plotly_chart(fig, *, container=None, pareto: bool | None = None, glossary: bool = True,
                 decision_key: str | None = None, decision: bool = True, **kwargs):
    """Draw `fig` — THE way every chart of the app reaches the screen (R243).

    R314 — and says, under it, what it lets you decide (`chart_decisions.py`), looked up by
    the caller's site key, or by `decision_key` for a helper drawn on several pages."""
    import streamlit as st

    from src.dashboard.utils.i18n import t
    target = container if container is not None else st
    if fig is not None and hasattr(fig, "layout"):
        apply_defaults(fig, pareto=pareto)
    out = target.plotly_chart(fig, **kwargs)
    if decision:                # False only where the owner asked the page for no text (R421)
        _say_the_decision(target, decision_key)
    if glossary and fig is not None and hasattr(fig, "layout"):
        terms = jargon(fig)
        if terms:
            target.caption(" · ".join(t(GLOSSARY[k][0], GLOSSARY[k][1]) for k in terms))
    return out


def pyplot(fig, *, container=None, decision_key: str | None = None, **kwargs):
    """Draw a matplotlib `fig` through the same door (R314: the SHAP charts had bypassed it,
    so they would have been the only charts without their decision line)."""
    import streamlit as st
    target = container if container is not None else st
    out = target.pyplot(fig, **kwargs)
    _say_the_decision(target, decision_key)
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
