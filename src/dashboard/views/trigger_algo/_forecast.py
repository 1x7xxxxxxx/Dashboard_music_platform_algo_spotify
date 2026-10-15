"""Road to Algo — a track's cumulative streams and revenue, from J+7 to 10 years (R570).

Type: Sub
Uses: numpy, pandas, plotly, src.dashboard.utils.artist_cashflow (track_stream_rate),
      ._tab_algo_streams (load_estimates, TRIGGER_ORDER)
Reads: v_s4a_song_daily (gold view over the S4A CSVs) — in `show_forecast`, the function
       that draws, so the gold-coverage map can attribute the figure
Triggers: views/trigger_algo/router.py (« Où en sont mes titres », once per picked release)
Persists in: nothing

Owner, 2026-10-15 : « écoutes cumulées + revenus » of each release at J+7, J+28, 3 months,
6 months, 1 year, 5 and 10 years, on a log time axis. The base is the track's OWN decay —
a power law `streams/day = c · (age/t0)^-b` fitted on its last 90 imported days — with a
P25–P75 band from the slope's standard error (± 0.674 SE). An age already past is the
MEASURED cumulative, never a projection.

The « if DW / Radio / RR triggers » overlays come from `algo_stream_estimates.json` and
exist ONLY at the ages it was measured at — the first month (j28) and around 6 months
(m6). The 1-year age was refused by the export (too few tracks) and Release Radar at
6 months has n = 0: nothing is extrapolated to 10 years from a 28-day median.

Revenue is written on each point (and in its hover), never on a second axis: the app
refuses secondary axes (`tests/test_the_visual_rules_only_tighten.py`), and a constant
rate would only relabel the same curve.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.dashboard.utils.i18n import t

#: (key, track age in days, FR label) — the horizons the owner named.
HORIZONS = (("j7", 7, "J+7"), ("j28", 28, "J+28"), ("m3", 91, "3 mois"),
            ("m6", 182, "6 mois"), ("y1", 365, "1 an"), ("y5", 1826, "5 ans"),
            ("y10", 3652, "10 ans"))
#: The estimate ages an overlay may sit on, and the horizon each one lands on.
OVERLAY_AGES = {"j28": 28, "m6": 182}
FIT_WINDOW = 90      # days of history the decay is fitted on
MIN_POINTS = 14      # below this, the fit falls back to the recent mean (flat)
_Z_QUARTILE = 0.674  # P25/P75 of a normal, in standard errors
_MAX_SLOPE = 3.0


def daily_by_age(daily: pd.DataFrame, release) -> pd.DataFrame:
    """age (days since release, ≥ 0) and streams, one row per imported day. Pure.

    Without a release date, the first imported day stands for it."""
    if daily is None or daily.empty:
        return pd.DataFrame(columns=["age", "streams"])
    days = pd.to_datetime(daily["day"])
    start = pd.Timestamp(release) if release is not None else days.min()
    out = pd.DataFrame({"age": (days - start).dt.days,
                        "streams": pd.to_numeric(daily["streams"], errors="coerce").fillna(0)})
    return out[out["age"] >= 0].sort_values("age").reset_index(drop=True)


def fit_decay(hist: pd.DataFrame) -> dict | None:
    """The track's decay over its last `FIT_WINDOW` days. Pure.

    `{kind: power, c, b, se, t0}` — log-linear fit centred on the window's geometric-mean
    age, so moving the slope pivots the curve INSIDE the measured window — or
    `{kind: flat, level}` with too few positive days. A rising track is held flat
    (b ≥ 0): ten years of growth extrapolated from three months is not a forecast."""
    if hist is None or hist.empty:
        return None
    last = int(hist["age"].max())
    recent = hist[hist["age"] > last - FIT_WINDOW]
    pos = recent[(recent["streams"] > 0) & (recent["age"] >= 1)]
    if len(pos) < MIN_POINTS:
        return {"kind": "flat", "level": float(recent["streams"].mean() or 0.0)}
    x = np.log(pos["age"].to_numpy(float))
    y = np.log(pos["streams"].to_numpy(float))
    t0 = float(np.exp(x.mean()))
    xc = x - x.mean()
    slope = float((xc * (y - y.mean())).sum() / (xc ** 2).sum())
    resid = y - (y.mean() + slope * xc)
    se = float(math.sqrt((resid ** 2).sum() / (len(x) - 2) / (xc ** 2).sum()))
    b = min(max(-slope, 0.0), _MAX_SLOPE)
    return {"kind": "power", "c": float(np.exp(y.mean())), "b": b, "se": se, "t0": t0}


def projected_sum(fit: dict, from_age: int, to_age: int, shift: float = 0.0) -> float:
    """Streams the fit expects from `from_age` (excluded) to `to_age` (included). Pure.

    `shift` moves the decay slope by that many units (the P25–P75 band)."""
    if to_age <= from_age:
        return 0.0
    if fit["kind"] == "flat":
        return fit["level"] * (to_age - from_age)
    b = min(max(fit["b"] + shift, 0.0), _MAX_SLOPE)
    ages = np.arange(from_age + 1, to_age + 1, dtype=float)
    return float((fit["c"] * (ages / fit["t0"]) ** -b).sum())


def cumulative_path(hist: pd.DataFrame, fit: dict | None) -> list[dict]:
    """One point per horizon: measured when the age is past, projected after. Pure.

    Each point: key, age, label, value, lo, hi (the band — equal to value when
    measured or flat), measured (bool)."""
    if hist is None or hist.empty or fit is None:
        return []
    last = int(hist["age"].max())
    cum = hist.groupby("age")["streams"].sum().cumsum()
    done = float(cum.iloc[-1])
    spread = _Z_QUARTILE * fit.get("se", 0.0) if fit["kind"] == "power" else 0.0
    out = []
    for key, age, fr in HORIZONS:
        label = t(f"trigger_algo.fc.h.{key}", fr)
        if age <= last:
            v = float(cum[cum.index <= age].iloc[-1]) if (cum.index <= age).any() else 0.0
            out.append({"key": key, "age": age, "label": label, "value": v,
                        "lo": v, "hi": v, "measured": True})
            continue
        # a STEEPER slope (+spread) is the pessimistic quartile
        out.append({"key": key, "age": age, "label": label, "measured": False,
                    "value": done + projected_sum(fit, last, age),
                    "lo": done + projected_sum(fit, last, age, +spread),
                    "hi": done + projected_sum(fit, last, age, -spread)})
    return out


def algo_overlays(est: dict, path: list[dict], last_age: int, order: tuple) -> list[dict]:
    """« If this playlist triggers » markers, only at a measured estimate age still ahead.

    Each: algo, age, y (base cumulative + P50), y_lo, y_hi (+ P25, + P75), n. Pure."""
    ests = (est or {}).get("estimates") or {}
    base = {p["age"]: p["value"] for p in path}
    out = []
    for algo in order:
        for key, age in OVERLAY_AGES.items():
            cell = (ests.get(algo.lower()) or {}).get(key) or {}
            if cell.get("refused") or "p50" not in cell or age <= last_age or age not in base:
                continue
            out.append({"algo": algo, "age_key": key, "age": age, "n": cell.get("n"),
                        "y": base[age] + cell["p50"], "y_lo": base[age] + cell["p25"],
                        "y_hi": base[age] + cell["p75"]})
    return out


def _point_text(p: dict, rate: float | None) -> str:
    from src.dashboard.utils.formats import eur, num
    txt = num(p["value"], 0)
    return txt + (f"<br>{eur(p['value'] * rate, 0)}" if rate else "")


def _base_traces(fig, path: list[dict], rate: float | None, below: set = frozenset()) -> None:
    """The measured part (solid), the projected part (dotted) and its P25–P75 band.

    A point at an age in `below` writes its label UNDER it: an overlay sits above."""
    import plotly.graph_objects as go
    done = [p for p in path if p["measured"] and p["value"] > 0]
    ahead = [p for p in path if not p["measured"] and p["value"] > 0]
    joint = done[-1:] + ahead
    if ahead:
        xs = [p["age"] for p in joint]
        fig.add_trace(go.Scatter(
            x=xs + xs[::-1], y=[p["hi"] for p in joint] + [p["lo"] for p in joint][::-1],
            fill="toself", fillcolor="rgba(120,120,120,0.18)", line=dict(width=0),
            hoverinfo="skip", name=t("trigger_algo.fc.band", "Fourchette P25–P75 de la prévision")))
    for part, dash, name in ((done, "solid", t("trigger_algo.fc.measured", "Mesuré")),
                             (joint if ahead else [], "dot",
                              t("trigger_algo.fc.projected", "Prévu — rythme actuel du titre"))):
        if not part:
            continue
        fig.add_trace(go.Scatter(
            x=[p["age"] for p in part], y=[p["value"] for p in part], name=name,
            mode="lines+markers+text", line=dict(color="#444", dash=dash, width=2),
            # the dotted part starts ON the last measured point: label it once
            text=[_point_text(p, rate) if p["measured"] == (dash == "solid") else ""
                  for p in part],
            textposition=["bottom right" if p["age"] in below else "top center" for p in part],
            cliponaxis=False, customdata=[p["label"] for p in part],
            hovertext=[_point_text(p, rate).replace("<br>", " · ") for p in part],
            hovertemplate="%{customdata} : %{hovertext}<extra></extra>"))


def _overlay_traces(fig, overlays: list[dict]) -> None:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import ALGO_COLORS
    from src.utils.algo_order import ALGO_NAMES
    algos = list(dict.fromkeys(o["algo"] for o in overlays))
    for i, algo in enumerate(algos):
        mine = [o for o in overlays if o["algo"] == algo]
        dodge = 1 + 0.12 * (i - (len(algos) - 1) / 2)   # side by side on the log axis
        fig.add_trace(go.Scatter(
            x=[o["age"] * dodge for o in mine], y=[o["y"] for o in mine], mode="markers",
            marker=dict(color=ALGO_COLORS[algo], size=12, symbol="diamond"),
            error_y=dict(type="data", symmetric=False, color=ALGO_COLORS[algo],
                         array=[o["y_hi"] - o["y"] for o in mine],
                         arrayminus=[o["y"] - o["y_lo"] for o in mine]),
            name=t("trigger_algo.fc.if_algo", "Si {algo} se déclenche (P50, barre P25–P75)")
            .format(algo=ALGO_NAMES[algo]),
            hovertemplate=ALGO_NAMES[algo] + " : %{y:,.0f}<extra></extra>"))


def forecast_figure(path: list[dict], overlays: list[dict], rate: float | None = None):
    """Cumulative streams on log-log axes; revenue written on each point at `rate`. Pure."""
    import plotly.graph_objects as go
    fig = go.Figure()
    _base_traces(fig, path, rate, {o["age"] for o in overlays})
    _overlay_traces(fig, overlays)
    ys = [v for p in path for v in (p["lo"], p["hi"], p["value"]) if v > 0]
    ys += [o["y_hi"] for o in overlays]
    if not ys:
        return fig
    yr = [math.log10(min(ys)) - 0.15, math.log10(max(ys)) + 0.35]
    fig.update_xaxes(type="log", tickvals=[a for _k, a, _l in HORIZONS],
                     ticktext=[t(f"trigger_algo.fc.h.{k}", fr) for k, _a, fr in HORIZONS],
                     range=[math.log10(4.2), math.log10(5600)])
    fig.update_yaxes(type="log", range=yr,
                     title_text=t("trigger_algo.fc.axis", "Écoutes cumulées depuis la sortie"))
    fig.update_layout(height=430, margin=dict(t=30, r=60))
    return fig


def _forecast_note(fit: dict, rate: dict | None, overlays: list[dict]) -> str:
    from src.dashboard.utils.formats import num
    parts = [t("trigger_algo.fc.note_power",
               "Base : le déclin propre du titre, ajusté sur ses {d} derniers jours importés.")
             .format(d=FIT_WINDOW) if fit["kind"] == "power" else
             t("trigger_algo.fc.note_flat",
               "Trop peu de jours d'écoute pour mesurer un déclin : la base prolonge la "
               "moyenne récente, sans fourchette.")]
    if not rate:
        parts.append(t("trigger_algo.fc.no_rate",
                       "Revenus non affichés : aucun taux par écoute mesurable (aucun relevé "
                       "de revenus importé)."))
    else:
        r = num(rate["eur_par_stream"], 5)
        parts.append(t("trigger_algo.fc.rate_track",
                       "Revenus au taux mesuré de ce titre ({r} € par écoute).").format(r=r)
                     if rate.get("source") == "track" else
                     t("trigger_algo.fc.rate_artist",
                       "Revenus au taux moyen de l'artiste ({r} € par écoute) — ce titre n'a "
                       "pas encore de relevé propre.").format(r=r))
    if not overlays:
        parts.append(t("trigger_algo.fc.no_overlay",
                       "Pas de losange « si la playlist se déclenche » : le titre a passé les "
                       "âges où un déclenchement a été mesuré (1er mois, vers 6 mois)."))
    return " ".join(parts)


def show_forecast(db, artist_id: int, song: str, release) -> None:
    """The forecast of ONE picked release — read here, drawn here (gold coverage)."""
    import streamlit as st

    from src.dashboard.utils import charts
    from src.dashboard.utils.artist_cashflow import track_stream_rate
    from src.utils.algo_order import ALGO_ORDER

    from ._tab_algo_streams import load_estimates
    st.markdown(t("trigger_algo.fc.head",
                  "**🔮 Prévision — écoutes cumulées et revenus de {song}**").format(song=song))
    daily = db.fetch_df(
        "SELECT day, streams FROM v_s4a_song_daily WHERE artist_id = %s AND song = %s "
        "ORDER BY day", (artist_id, song))
    hist = daily_by_age(daily, release)
    fit = fit_decay(hist)
    path = cumulative_path(hist, fit)
    if not path:
        st.info(t("trigger_algo.fc.empty",
                  "Aucune écoute importée pour ce titre : pas de prévision."))
        return
    overlays = algo_overlays(load_estimates(), path, int(hist["age"].max()), ALGO_ORDER)
    rate = track_stream_rate(db, artist_id, song)
    fig = forecast_figure(path, overlays, rate["eur_par_stream"] if rate else None)
    charts.plotly_chart(fig, width="stretch")
    st.caption(_forecast_note(fit, rate, overlays))
