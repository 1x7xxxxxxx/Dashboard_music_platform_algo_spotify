"""The cross view's whole funnel — from the euro spent to the euro earned back (R556).

Type: Utility
Uses: pandas, plotly, src.dashboard.utils.campaign_funnel (streams_gained),
      src.dashboard.utils.artist_cashflow (stream_rate), src.dashboard.utils.i18n
Triggers: views/meta_x_spotify.py (`_render_funnel`, `render_funnel` — the comparison)
R575: `figure` is a real `go.Funnel` — the nested counts narrow top to bottom.
Persists in: nothing

Owner's Y2 of 2026-10-13, fiches 44, 43, 128, 22, 23, 39, 26: « budget → impressions →
clics lien → visites smart link → clics plateformes → streams → revenus, chaque étape
avec X % de l'étape d'avant expliqué et son coût par unité ». Seven steps, three units:

  · budget and revenue are EUROS — the first and the last word of the story;
  · impressions → link clicks → smart-link arrivals → platform clicks are NESTED counts:
    « X % de l'étape d'avant » means « out of 100 at the step before, X went on »;
  · streams are NOT nested in the platform clicks (one visitor streams many times, and
    the organic rise is in it too — the render once read « 191 % »): they are said as
    « écoutes par clic plateforme », never as a %.

Revenue is streams gained × the €/stream MEASURED on the distributor's sales
(`artist_cashflow.stream_rate`), never a monthly revenue joined onto days (critic, R556).
A step at 0 or unmeasured is not drawn: it would draw a collapse that did not happen.
"""
from __future__ import annotations

import math

import plotly.graph_objects as go

from src.dashboard.utils.i18n import t
from src.dashboard.utils.platform_colors import platform_color

# key, unit ("eur" | "count"), nested in the step before (a % is meaningful)
STEPS = (
    ("budget", "eur", False),
    ("impressions", "count", False),
    ("reach", "count", True),
    ("link_clicks", "count", True),
    ("arrivals", "count", True),
    ("store_clicks", "count", True),
    ("streams", "count", False),
    ("revenue", "eur", False),
)
_META_STEPS = ("impressions", "link_clicks")   # the steps Meta's breakdowns describe
_INK = {"budget": "#FF6D00", "impressions": platform_color("meta"),
        "reach": platform_color("meta"),
        "link_clicks": platform_color("meta"), "arrivals": "#7C4DFF",
        "store_clicks": "#7C4DFF", "streams": platform_color("spotify"), "revenue": "#2E7D32"}


def _label(key: str) -> str:
    return {
        "budget": t("full_funnel.budget", "Budget dépensé"),
        "impressions": t("full_funnel.impressions", "Impressions"),
        "reach": t("full_funnel.reach", "Couverture (personnes touchées)"),
        "link_clicks": t("full_funnel.link_clicks", "Clics sur la pub"),
        "arrivals": t("full_funnel.arrivals", "Visites du smart link"),
        "store_clicks": t("full_funnel.store_clicks", "Clics du smart link"),
        "streams": t("full_funnel.streams", "Écoutes gagnées"),
        "revenue": t("full_funnel.revenue", "Revenus de ces écoutes"),
    }[key]


def _n(v: float, digits: int = 0) -> str:
    return f"{v:,.{digits}f}".replace(",", " ").replace(".", ",")


def steps(m: dict, eur_per_stream: float | None, best: dict | None = None) -> list[dict]:
    """The drawn steps, in order: {key, label, value, text}. Pure.

    `m` holds spend, impressions, link_clicks, arrivals, store_clicks, streams (gained);
    any may be None. Revenue exists only with streams AND a measured €/stream. `best`
    ({step: label}, R567) writes the cheapest age / country / placement on the step
    Meta measured it at — never on a step Meta does not see."""
    vals = dict(m)
    vals["budget"] = m.get("spend")
    streams = m.get("streams")
    vals["revenue"] = (streams * eur_per_stream
                       if streams and streams > 0 and eur_per_stream else None)
    spend = m.get("spend") or None
    out, prev = [], None
    for key, unit, nested in STEPS:
        v = vals.get(key)
        if v is None or v <= 0:
            # An unmeasured reach (old exports) does not break impressions → clicks.
            prev = prev if key == "reach" else None if nested or key == "impressions" else prev
            continue
        parts = [_n(v, 2) + " €" if unit == "eur" else _n(v)]
        if nested and prev:
            parts.append(t("full_funnel.kept", "{p} % de l'étape d'avant").format(
                p=_n(100 * v / prev, 1)))
        if key == "impressions" and spend:
            parts.append(t("full_funnel.cpm", "{c} € les 1 000").format(c=_n(spend / v * 1000, 2)))
        elif unit == "count" and spend:
            parts.append(t("full_funnel.unit", "{c} € l'unité").format(c=_n(spend / v, 3)))
        if key == "streams" and vals.get("store_clicks"):
            parts.append(t("full_funnel.per_click", "{r} écoutes par clic smart link").format(
                r=_n(v / vals["store_clicks"], 1)))
        if key == "revenue" and spend:
            parts.append(t("full_funnel.recovered", "{p} % du budget récupéré").format(
                p=_n(100 * v / spend, 1)))
        if key == "reach":
            parts.append(t("full_funnel.reach_days", "somme des jours"))
        if key in _META_STEPS and (best or {}).get(key):
            parts.append(best[key])
        out.append({"key": key, "label": _label(key), "value": float(v),
                    "text": " · ".join(parts)})
        prev = v if unit == "count" else None
    return out


def indicators(m: dict) -> list[tuple[str, str]]:
    """Fiche 26's six numbers for one campaign: spend, impressions, clicks, CPM, CPC, CPR."""
    spend, imp = m.get("spend"), m.get("impressions")
    clicks, capi = m.get("link_clicks"), m.get("capi")
    per = lambda num, den, k=1: _n(num / den * k, 2) + " €" if num and den else "—"  # noqa: E731
    return [(t("full_funnel.i_spend", "Dépense"), _n(spend, 2) + " €" if spend else "—"),
            (t("full_funnel.i_imp", "Impressions"), _n(imp) if imp else "—"),
            (t("full_funnel.i_clicks", "Clics"), _n(clicks) if clicks else "—"),
            ("CPM", per(spend, imp, 1000)), ("CPC", per(spend, clicks)),
            ("CPR", per(spend, capi))]


def widths(values: list[float]) -> list[float]:
    """Funnel widths, wide to narrow: log-scaled so 40 clicks under 100 000 impressions
    stay visible, and never wider than the step above (a funnel narrows). Pure."""
    top = math.log10(max(values) + 1) or 1.0
    out: list[float] = []
    for v in values:
        w = max(8.0, 100 * math.log10(v + 1) / top)
        out.append(min(w, out[-1]) if out else w)
    return out


def figure(drawn: list[dict], height: int = 460) -> go.Figure | None:
    """One funnel, every step in order, top to bottom (R589 — owner, 2026-10-15: « le
    budget en tête comme une case, puis impressions, couverture, clics, visites, clics
    smart link, écoutes, revenus »). None under 2 steps.

    The budget is the widest case — every step below is bought with it. Counts are
    log-scaled and never wider than the step above; streams and revenue sit in the same
    column, narrower still: their text says why they are not a % of the clicks (the
    render once read « 191 % »). The number written on each step is its real value."""
    if len(drawn) < 2:
        return None
    counts = [s for s in drawn if s["key"] not in ("budget", "revenue")]
    w = dict(zip([s["key"] for s in counts], widths([s["value"] for s in counts])))
    xs: list[float] = []
    for s in drawn:   # counts sit under the budget case (92 %), revenue under the streams
        x = 100.0 if s["key"] == "budget" else 0.92 * w.get(s["key"], xs[-1] if xs else 100)
        xs.append(max(8.0, min(x, xs[-1])) if xs else x)
    fig = go.Figure(go.Funnel(
        y=[s["label"] for s in drawn], x=xs,
        text=[s["text"] for s in drawn], textinfo="text", textposition="inside",
        textfont={"size": 15}, insidetextanchor="middle",
        marker_color=[_INK[s["key"]] for s in drawn],
        connector={"line": {"width": 0}, "fillcolor": "rgba(0,0,0,0.06)"},
        hoverinfo="text", hovertext=[f"{s['label']} : {s['text']}" for s in drawn]))
    fig.update_layout(height=height, showlegend=False, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis=dict(automargin=True, tickfont={"size": 14}))
    return fig
