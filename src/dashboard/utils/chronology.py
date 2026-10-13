"""The cross view's one chronology — every daily reading on one clock (R555).

Type: Utility
Uses: pandas, plotly, src.dashboard.utils.campaign_funnel (audience_flows),
      src.dashboard.utils.meta_impact, src.dashboard.utils.ratios (per_series)
Triggers: views/meta_ads_overview.py (`_render_chrono`)
Persists in: nothing

Owner's Y2 of 2026-10-13, fiches 42, 43 and 29: « un truc temporel qui regroupe tout […]
et pouvoir afficher ou non en légende les différentes data ». Three figures drew the same
days three times — the listener verdict (42), the campaign journey in base 100 (43) and
spend/clicks/CPR (29). One figure now, each series in its own `legendgroup`:

  · left axis, PER DAY (7-day means): listeners, streams, saves, playlist adds, followers
    gained, outbound clicks, Shazams — volumes, comparable with one another;
  · right axis, in EUROS: the budget per day as an area, and the CPR — a price.

The budget area replaces the orange bands of fiche 42 (« plusieurs lignes sur les jours de
pub, à quoi ça correspond ? »): a band per campaign overlapped its neighbours and said
nothing of the amount. Where the area is, the ads ran; its height is what they cost.
The age comparison (fiches 2, 6, 28) stays a SECOND figure: two x axes never share one.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils.campaign_funnel import audience_flows
from src.dashboard.utils.i18n import t
from src.dashboard.utils.platform_colors import DISTINCT, platform_color
from src.dashboard.utils.ratios import per_series

# The inks an artist already learned on fiches 42 and 29 (listeners violet, ad days
# orange, clicks green) — kept so the merged figure reads like its parts.
_LISTENER_INK = "#7C4DFF"
_BUDGET_INK = "#FF6D00"
_CLICK_INK = "#1baf7a"

# Shown on arrival; the rest is one legend click away (the owner's « afficher ou non »).
_SHOWN = frozenset({"listeners", "streams", "saves", "playlist_adds", "followers_level",
                    "budget"})

_AUDIENCE_SQL = (
    "SELECT day, listeners, streams, saves, playlist_adds, followers_level "
    "FROM v_s4a_audience_daily WHERE artist_id = %s ORDER BY day")
_SHAZAM_SQL = (
    "SELECT day, SUM(daily_shazams) AS shazams FROM v_apple_song_daily "
    "WHERE artist_id = %s AND days_since_previous = 1 GROUP BY day ORDER BY day")
# Every account, every campaign — the verdict judges the LAST campaign of all accounts:
# two overlapping campaigns cannot be told apart, whatever their account (R195).
_ALL_SPEND_SQL = (
    "SELECT ad_account_id, campaign_name, day, SUM(spend) AS spend FROM v_meta_daily "
    "WHERE spend > 0 AND artist_id = %s GROUP BY ad_account_id, campaign_name, day "
    "ORDER BY day")


def load(db, artist_id: int, scope_sql: str, scope_params: tuple) -> dict:
    """The four frames of the figure. `scope_sql` is the filter bar's suffix on
    `v_meta_daily` (account, campaigns, window): the budget and clicks follow the bar;
    the listeners, the flows and the verdict's campaigns do not (see `_ALL_SPEND_SQL`)."""
    meta = db.fetch_df(
        "SELECT day, SUM(spend) AS spend, SUM(custom_conversions) AS clicks "
        f"FROM v_meta_daily WHERE artist_id = %s{scope_sql} GROUP BY day ORDER BY day",
        (artist_id, *scope_params))
    return {"audience": db.fetch_df(_AUDIENCE_SQL, (artist_id,)),
            "shazam": db.fetch_df(_SHAZAM_SQL, (artist_id,)),
            "meta": meta,
            "all_spend": db.fetch_df(_ALL_SPEND_SQL, (artist_id,))}


def _daily(df: pd.DataFrame | None, col: str) -> pd.Series:
    """`col` per calendar day; a day with no row is NaN (a gap), never 0."""
    if df is None or df.empty or col not in df:
        return pd.Series(dtype=float)
    s = pd.to_numeric(df[col], errors="coerce")
    s.index = pd.to_datetime(df["day"])
    s = s.groupby(level=0).sum(min_count=1).sort_index()
    return s.reindex(pd.date_range(s.index.min(), s.index.max()))


def series(frames: dict) -> dict[str, tuple[str, pd.Series]]:
    """{key: (label, daily series)} — pure. Flows are 7-day means; money is per day."""
    out: dict[str, tuple[str, pd.Series]] = {}
    listeners = _daily(frames.get("audience"), "listeners")
    if not listeners.empty:
        out["listeners"] = (t("chronology.listeners", "Auditeurs / jour (moyenne 7 j)"),
                            listeners.rolling(7, min_periods=4).mean())
    out.update(audience_flows(frames.get("audience")))
    shazam = _daily(frames.get("shazam"), "shazams")
    if not shazam.empty:
        out["shazam"] = (t("chronology.shazam", "Shazams / jour"), shazam)
    spend, clicks = _daily(frames.get("meta"), "spend"), _daily(frames.get("meta"), "clicks")
    if not spend.empty:
        out["clicks"] = (t("chronology.clicks", "Clics sortants / jour"), clicks)
        out["budget"] = (t("chronology.budget", "Budget Meta (€ / jour)"), spend)
        out["cpr"] = (t("chronology.cpr", "CPR (€ / clic sortant)"),
                      per_series(spend, clicks))
    return out


def _style(key: str) -> dict:
    """The trace arguments of one series: mode, axis, ink."""
    inks = {"listeners": _LISTENER_INK, "streams": platform_color("spotify"),
            "saves": DISTINCT[1], "playlist_adds": DISTINCT[2],
            "followers_level": DISTINCT[3], "clicks": _CLICK_INK,
            "shazam": platform_color("apple"), "cpr": DISTINCT[0]}
    if key == "budget":
        return dict(mode="lines", fill="tozeroy", yaxis="y2", line=dict(width=0.5,
                    color=_BUDGET_INK), fillcolor="rgba(255,109,0,0.22)")
    if key == "shazam":
        return dict(mode="markers", marker=dict(size=6, color=inks[key]))
    if key == "cpr":
        return dict(mode="lines+markers", yaxis="y2", marker=dict(size=5),
                    line=dict(color=inks[key], width=2, dash="dot"))
    return dict(mode="lines", line=dict(color=inks[key], width=2.5 if key ==
                                        "listeners" else 1.8))


def figure(frames: dict, x_range: tuple | None = None) -> go.Figure | None:
    """The one chronology, or None when nothing is measured. Pure (no database)."""
    drawn = series(frames)
    if not drawn:
        return None
    fig = go.Figure()
    for key, (label, s) in drawn.items():
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, name=label, legendgroup=key, connectgaps=False,
            visible=True if key in _SHOWN else "legendonly", **_style(key)))
    fig.update_layout(
        height=480, hovermode="x unified",
        yaxis=dict(title=t("chronology.axis_left", "Par jour (moyenne 7 j)")),
        yaxis2=dict(title=t("chronology.axis_right", "€"), overlaying="y", side="right",
                    showgrid=False, rangemode="tozero", title_font=dict(color=_BUDGET_INK),
                    tickfont=dict(color=_BUDGET_INK)),
        margin=dict(t=40))
    if x_range is not None:
        fig.update_layout(xaxis_range=list(x_range))
    return fig


def default_range(frames: dict, window) -> tuple | None:
    """The bar's window; on « all history », the last campaign from 60 days before it."""
    if window is not None and not window.is_all_history:
        return (pd.Timestamp(window.start), pd.Timestamp(window.end))
    spend = _daily(frames.get("all_spend"), "spend").dropna()
    listeners = _daily(frames.get("audience"), "listeners").dropna()
    if spend.empty:
        return None
    from src.dashboard.utils import meta_impact
    last = meta_impact.campaigns(frames["all_spend"])[-1]
    end = max([spend.index.max()] + ([listeners.index.max()] if not listeners.empty else []))
    return (pd.Timestamp(last.start) - pd.Timedelta(days=60), end)
