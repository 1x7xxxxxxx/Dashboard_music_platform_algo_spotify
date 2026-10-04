"""Two campaigns side by side — ONE selector and the shaping behind it, for three Meta pages (R350).

Type: Utility
Uses: streamlit, pandas, plotly, utils.i18n.t, utils.ratios.per_series, utils.platform_colors
Depends on: the campaign list each page already reads (no query of its own)
Triggers: views/meta_ads_overview.py, views/meta_creatives.py, views/meta_breakdowns.py
Persists in: nothing (widget state only)

The owner's request (screen review, 2026-10-04): pick TWO campaigns and read them at a
comparable scale on « Performance Globale », and get a second campaign filter on « Visuels
de campagne » and « Qui a vu tes pubs ». One selector, not three copies: the three pages
call `second_campaign`, and its default is « none », so a page with one campaign chosen
renders exactly as before.

The comparable scale is CHOSEN, and said here so it can be contradicted:
  * totals (spend, clicks) are put on ONE clock — day 0 is each campaign's first euro
    spent, whatever the calendar date; a pause day is a 0, never a gap (the R349 rule);
  * costs (CPC) are recomputed from the two running sums, never averaged per day;
  * a breakdown is compared as a SHARE of each campaign's own total — 300 € and 30 €
    campaigns cannot share an absolute axis, their distributions can.
The pure functions below take frames and return frames; the two renderers only draw.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils import charts
from src.dashboard.utils.i18n import t
from src.dashboard.utils.platform_colors import DISTINCT
from src.dashboard.utils.ratios import per_series

# Campaign A then campaign B — the two first colours of the shared palette.
PAIR_COLORS: tuple[str, str] = (DISTINCT[0], DISTINCT[1])
_ALL = "Toutes"   # the « every campaign » sentinel the pages already use


def pair_options(options: list, first: str | None) -> list:
    """What the second selector offers: « none » first, then every OTHER campaign."""
    return [None] + [c for c in options if c and c != first]


def second_campaign(options: list, first: str | None, key: str) -> str | None:
    """The shared « compare with » selector. None (the default) leaves the page unchanged.

    Shown only once ONE campaign is chosen: comparing « all campaigns » with one of them
    has no meaning. The pick is re-checked against `options` (rule #8 — it is a value
    from the database that ends up as a query parameter)."""
    if not first or first == _ALL:
        return None
    offered = pair_options(options, first)
    if len(offered) < 2:
        return None
    pick = st.selectbox(
        t("campaign_pair.second", "Comparer avec une 2ᵉ campagne"), offered, key=key,
        format_func=lambda c: t("campaign_pair.none", "— aucune —") if c is None else c)
    return pick if pick in offered[1:] else None


BOTH_COLOR = "#7f7f7f"   # a creative that ran in BOTH campaigns belongs to neither colour


def pair_colors(names: list, rows: pd.DataFrame, first: str, second: str) -> list[str]:
    """One colour per creative name: campaign A, campaign B, or grey when it ran in both.

    `rows` holds (creative_name, campaign_name); a page that ranks ONE bar per creative
    (R241) still has to say which campaign the bar belongs to."""
    owners = rows.groupby("creative_name")["campaign_name"].agg(set)
    out = []
    for n in names:
        own = owners.get(n, set())
        out.append(BOTH_COLOR if {first, second} <= own else
                   PAIR_COLORS[0] if first in own else
                   PAIR_COLORS[1] if second in own else BOTH_COLOR)
    return out


def day0_cumulative(daily: pd.DataFrame, first: str, second: str | None) -> pd.DataFrame:
    """[campaign, offset, spend_cum, clicks_cum, cpc_cum] — each campaign on ITS day 0.

    `daily` holds (campaign_name, day, spend, link_clicks), one row per campaign-day.
    Day 0 is the first day with spend > 0; days before it are dropped, a day without a
    row inside the life is a 0 (pause), never interpolated."""
    out = []
    for name in [c for c in (first, second) if c]:
        mine = daily[daily["campaign_name"] == name].copy()
        mine["day"] = pd.to_datetime(mine["day"])
        for c in ("spend", "link_clicks"):
            mine[c] = pd.to_numeric(mine[c], errors="coerce").fillna(0)
        spent = mine.loc[mine["spend"] > 0, "day"]
        if spent.empty:
            continue
        j0, last = spent.min(), mine["day"].max()
        per_day = (mine[mine["day"] >= j0].groupby("day")[["spend", "link_clicks"]].sum()
                   .reindex(pd.date_range(j0, last, freq="D"), fill_value=0))
        frame = pd.DataFrame({
            "campaign": name,
            "offset": (per_day.index - j0).days,
            "spend_cum": per_day["spend"].cumsum().to_numpy(),
            "clicks_cum": per_day["link_clicks"].cumsum().to_numpy(),
        })
        frame["cpc_cum"] = per_series(frame["spend_cum"], frame["clicks_cum"])
        out.append(frame)
    if not out:
        return pd.DataFrame(columns=["campaign", "offset", "spend_cum", "clicks_cum", "cpc_cum"])
    return pd.concat(out, ignore_index=True)


def share_pair(a: pd.DataFrame, b: pd.DataFrame, label_col: str, value_col: str,
               top: int = 8) -> pd.DataFrame:
    """[label, share_a, share_b] in % of EACH side's own total, the `top` biggest labels.

    A label absent on one side is a 0 % there (it was measured: none of that campaign's
    money went there). A side whose total is 0 gives NaN — no distribution to compare."""
    sums = {side: pd.to_numeric(d[value_col], errors="coerce").fillna(0)
                    .groupby(d[label_col]).sum() for side, d in (("share_a", a), ("share_b", b))}
    both = pd.DataFrame(sums)
    for side, v in sums.items():
        total = float(v.sum())
        both[side] = both[side].fillna(0) * 100.0 / total if total > 0 else float("nan")
    both["_rank"] = both[["share_a", "share_b"]].max(axis=1)
    # A label at 0 % on both sides is an empty row in the figure, not a comparison.
    both = both[~(both["_rank"] <= 0)]
    both = both.sort_values("_rank", ascending=False).head(top).drop(columns="_rank")
    return both.rename_axis("label").reset_index()


_DAY0_COLS = ("spend_cum", "clicks_cum", "cpc_cum")


def _day0_titles() -> list[str]:
    """One title per frame, in `_DAY0_COLS` order — literal keys, so the i18n guard sees them."""
    return [t("campaign_pair.day0.spend_cum", "Dépense cumulée (€)"),
            t("campaign_pair.day0.clicks_cum", "Clics lien cumulés"),
            t("campaign_pair.day0.cpc_cum", "CPC cumulé (€)")]


def render_day0(curves: pd.DataFrame, first: str, second: str) -> None:
    """Three frames, one unit each — the two campaigns as two lines on the day-0 clock."""
    from plotly.subplots import make_subplots

    if curves.empty or curves["campaign"].nunique() < 2:
        st.caption(t("campaign_pair.day0_missing",
                     "Une des deux campagnes n'a aucun jour de dépense : rien à aligner."))
        return
    titles = _day0_titles()
    fig = make_subplots(rows=1, cols=3, horizontal_spacing=0.08, subplot_titles=titles)
    for i, (col, lab) in enumerate(zip(_DAY0_COLS, titles), start=1):
        for name, color in zip((first, second), PAIR_COLORS):
            s = curves[curves["campaign"] == name]
            fig.add_trace(go.Scatter(
                x=s["offset"], y=s[col], mode="lines", name=name, legendgroup=name,
                showlegend=i == 1, line={"color": color, "width": 2}, connectgaps=False,
                hovertemplate=f"J+%{{x}}<br>{lab} : %{{y}}<extra>{name[:30]}</extra>"),
                row=1, col=i)
        fig.update_xaxes(title_text=t("campaign_pair.day0_axis", "Jours depuis J0"),
                         rangemode="tozero", row=1, col=i)
    # automargin alone left the first frame's tick labels clipped at l=10 (seen on the PNG).
    fig.update_layout(height=360, margin={"l": 50, "r": 10, "t": 60, "b": 20},
                      legend={"orientation": "h", "y": -0.25})
    fig.update_yaxes(automargin=True)
    charts.plotly_chart(fig, width="stretch")


def render_share_pair(panels: dict, first: str, second: str) -> None:
    """One frame per breakdown: the two campaigns' shares, side by side, same % axis."""
    from plotly.subplots import make_subplots

    panels = {k: v for k, v in panels.items() if v is not None and not v.empty}
    if not panels:
        return
    fig = make_subplots(rows=1, cols=len(panels), horizontal_spacing=0.12,
                        subplot_titles=list(panels))
    for i, frame in enumerate(panels.values(), start=1):
        frame = frame.iloc[::-1]          # biggest on top (Plotly stacks from the bottom)
        for name, col, color in ((first, "share_a", PAIR_COLORS[0]),
                                 (second, "share_b", PAIR_COLORS[1])):
            fig.add_trace(go.Bar(
                x=frame[col], y=frame["label"], orientation="h", name=name,
                legendgroup=name, showlegend=i == 1, marker={"color": color},
                hovertemplate=f"%{{y}} : %{{x:.0f}} %<extra>{name[:30]}</extra>"),
                row=1, col=i)
        fig.update_xaxes(ticksuffix=" %", rangemode="tozero", row=1, col=i)
    fig.update_layout(barmode="group", height=380, bargap=0.25,
                      margin={"l": 10, "r": 10, "t": 60, "b": 20},
                      legend={"orientation": "h", "y": -0.2})
    fig.update_yaxes(automargin=True)
    charts.plotly_chart(fig, width="stretch")
