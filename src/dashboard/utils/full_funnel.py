"""The cross view's whole funnel — from the euro spent to the euro earned back (R556).

Type: Utility
Uses: pandas, plotly, src.dashboard.utils.campaign_funnel (streams_gained),
      src.dashboard.utils.artist_cashflow (stream_rate), src.dashboard.utils.i18n
Triggers: views/meta_x_spotify.py (`_render_funnel`, `render_funnel` — the comparison)
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

import plotly.graph_objects as go

from src.dashboard.utils.i18n import t
from src.dashboard.utils.platform_colors import platform_color

# key, unit ("eur" | "count"), nested in the step before (a % is meaningful)
STEPS = (
    ("budget", "eur", False),
    ("impressions", "count", False),
    ("link_clicks", "count", True),
    ("arrivals", "count", True),
    ("store_clicks", "count", True),
    ("streams", "count", False),
    ("revenue", "eur", False),
)
_META_STEPS = ("impressions", "link_clicks")   # the steps Meta's breakdowns describe
_INK = {"budget": "#FF6D00", "impressions": platform_color("meta"),
        "link_clicks": platform_color("meta"), "arrivals": "#7C4DFF",
        "store_clicks": "#7C4DFF", "streams": platform_color("spotify"), "revenue": "#2E7D32"}


def _label(key: str) -> str:
    return {
        "budget": t("full_funnel.budget", "Budget dépensé"),
        "impressions": t("full_funnel.impressions", "Impressions"),
        "link_clicks": t("full_funnel.link_clicks", "Clics sur la pub"),
        "arrivals": t("full_funnel.arrivals", "Visites du smart link"),
        "store_clicks": t("full_funnel.store_clicks", "Clics vers les plateformes"),
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
            prev = None if nested or key == "impressions" else prev
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
            parts.append(t("full_funnel.per_click", "{r} écoutes par clic plateforme").format(
                r=_n(v / vals["store_clicks"], 1)))
        if key == "revenue" and spend:
            parts.append(t("full_funnel.recovered", "{p} % du budget récupéré").format(
                p=_n(100 * v / spend, 1)))
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


def figure(drawn: list[dict], height: int = 420) -> go.Figure | None:
    """Horizontal bars on a log axis, the real value written on each. None under 2 steps.

    A log axis because the budget, 100 000 impressions and 40 platform clicks share it:
    on a linear one every step after the impressions is a sliver (dossier fiche 49)."""
    if len(drawn) < 2:
        return None
    fig = go.Figure(go.Bar(
        y=[s["label"] for s in drawn], x=[s["value"] for s in drawn], orientation="h",
        marker_color=[_INK[s["key"]] for s in drawn], text=[s["text"] for s in drawn],
        textposition="outside", cliponaxis=False, hoverinfo="text",
        hovertext=[f"{s['label']} : {s['text']}" for s in drawn]))
    top = max(s["value"] for s in drawn)
    fig.update_layout(
        height=height, showlegend=False, margin=dict(l=10, r=20, t=20, b=40),
        xaxis=dict(type="log", range=[0, len(f"{int(top)}") + 1.6], showticklabels=False,
                   title=t("full_funnel.log_axis",
                           "Longueur en échelle log — le chiffre écrit est la vraie valeur")),
        yaxis=dict(autorange="reversed", automargin=True))
    return fig
