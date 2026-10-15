"""Road to Algo — a track's cumulative streams and revenue, from J+7 to 10 years (R570).

Type: Sub
Uses: numpy, pandas, plotly, src.dashboard.utils.artist_cashflow (track_stream_rate),
      ._tab_algo_streams (load_estimates, TRIGGER_ORDER)
Reads: v_s4a_song_daily (gold view over the S4A CSVs) — in `show_forecast`, the function
       that draws, so the gold-coverage map can attribute the figure
Triggers: views/trigger_algo/router.py (« Où en sont mes titres », once for the picked releases)
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
from src.dashboard.utils.platform_colors import TYPE_COLOURS

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
            # R601 — a measured zero adds nothing to the path: no « if it triggers » mark.
            if (cell.get("refused") or cell.get("zero") or "p50" not in cell
                    or age <= last_age or age not in base):
                continue
            out.append({"algo": algo, "age_key": key, "age": age, "n": cell.get("n"),
                        "y": base[age] + cell["p50"], "y_lo": base[age] + cell["p25"],
                        "y_hi": base[age] + cell["p75"]})
    return out


def _point_text(p: dict, rate: float | None) -> str:
    from src.dashboard.utils.formats import eur, num
    txt = num(p["value"], 0)
    return txt + (f"<br>{eur(p['value'] * rate, 0)}" if rate else "")


#: R584 — one colour per title (the reference first), and the 5- and 10-year points in a
#: colour of their own: a long-term forecast, read as such (owner, 2026-10-15).
# R603 — the forecast follows the one registry (titles ≠ campaigns).
TITLE_COLORS = (TYPE_COLOURS["release.1"], TYPE_COLOURS["release.2"])
LONG_TERM_COLOR = TYPE_COLOURS["projection.long_term"]
LONG_TERM = frozenset({"y5", "y10"})


def _base_traces(fig, s: dict, below: set = frozenset(), under: set = frozenset()) -> None:
    """One title's measured part (solid), projected part (dotted) and P25–P75 band; its
    5- and 10-year points are marked in `LONG_TERM_COLOR`.

    A point at an age in `below` writes its label beside and under it (an overlay sits
    above); one in `under` writes it under (the other title's point sits above)."""
    import plotly.graph_objects as go
    path, rate, colour, name = s["path"], s.get("rate"), s["colour"], s["name"]
    done = [p for p in path if p["measured"] and p["value"] > 0]
    ahead = [p for p in path if not p["measured"] and p["value"] > 0]
    joint = done[-1:] + ahead
    if ahead:
        xs = [p["age"] for p in joint]
        fig.add_trace(go.Scatter(
            x=xs + xs[::-1], y=[p["hi"] for p in joint] + [p["lo"] for p in joint][::-1],
            fill="toself", fillcolor=_alpha(colour, 0.14), line=dict(width=0),
            hoverinfo="skip", legendgroup=name, showlegend=False))
    for part, dash in ((done, "solid"), (joint if ahead else [], "dot")):
        if not part:
            continue
        fig.add_trace(go.Scatter(
            x=[p["age"] for p in part], y=[p["value"] for p in part],
            name=name, legendgroup=name, showlegend=dash == "solid" or not done,
            mode="lines+markers+text", line=dict(color=colour, dash=dash, width=2),
            marker=dict(size=[13 if p["key"] in LONG_TERM else 7 for p in part],
                        color=[LONG_TERM_COLOR if p["key"] in LONG_TERM else colour
                               for p in part]),
            # the dotted part starts ON the last measured point: label it once
            text=[_point_text(p, rate) if p["measured"] == (dash == "solid") else ""
                  for p in part],
            textfont=dict(color=colour),
            textposition=["bottom right" if p["age"] in below else
                          "bottom center" if p["age"] in under else "top center" for p in part],
            cliponaxis=False, customdata=[p["label"] for p in part],
            hovertext=[_point_text(p, rate).replace("<br>", " · ") for p in part],
            hovertemplate=name + " · %{customdata} : %{hovertext}<extra></extra>"))


def _overlay_traces(fig, s: dict, shift: float = 1.0) -> None:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import ALGO_COLORS
    from src.utils.algo_order import ALGO_NAMES
    overlays = s["overlays"]
    algos = list(dict.fromkeys(o["algo"] for o in overlays))
    for i, algo in enumerate(algos):
        mine = [o for o in overlays if o["algo"] == algo]
        dodge = shift * (1 + 0.12 * (i - (len(algos) - 1) / 2))  # side by side, log axis
        fig.add_trace(go.Scatter(
            x=[o["age"] * dodge for o in mine], y=[o["y"] for o in mine], mode="markers",
            marker=dict(color=ALGO_COLORS[algo], size=12, symbol="diamond",
                        line=dict(color=s["colour"], width=2)),
            error_y=dict(type="data", symmetric=False, color=ALGO_COLORS[algo],
                         array=[o["y_hi"] - o["y"] for o in mine],
                         arrayminus=[o["y"] - o["y_lo"] for o in mine]),
            legendgroup=f"algo-{algo}", showlegend=shift == 1.0,
            name=t("trigger_algo.fc.if_algo", "Si {algo} se déclenche (P50, barre P25–P75)")
            .format(algo=ALGO_NAMES[algo]),
            hovertemplate=s["name"] + " · " + ALGO_NAMES[algo] + " : %{y:,.0f}<extra></extra>"))


def _long_term_key(fig) -> None:
    """A legend entry naming the long-term colour — the markers alone would not say it."""
    import plotly.graph_objects as go
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers",
        marker=dict(size=13, color=LONG_TERM_COLOR),
        name=t("trigger_algo.fc.long_term", "Prévision long terme (5 et 10 ans)")))


def _lower_ages(s: dict, series: list[dict]) -> set:
    """The ages where `s` lies under another title — its label goes below. Pure."""
    others = [{p["age"]: p["value"] for p in o["path"]} for o in series if o is not s]
    return {p["age"] for p in s["path"]
            if any(p["value"] < o.get(p["age"], -1) for o in others)}


def forecast_figure(series: list[dict]):
    """Every picked title's cumulative streams on ONE log-log figure (R584). Pure.

    `series`: one dict per title — name, path, overlays, rate (€ per stream or None),
    colour. Revenue is written on each point at the title's own rate."""
    import plotly.graph_objects as go
    fig = go.Figure()
    for i, s in enumerate(series):
        _base_traces(fig, s, {o["age"] for o in s["overlays"]}, _lower_ages(s, series))
        _overlay_traces(fig, s, shift=1.0 + 0.06 * i)
    if any(p["key"] in LONG_TERM for s in series for p in s["path"]):
        _long_term_key(fig)
    ys = [v for s in series for p in s["path"] for v in (p["lo"], p["hi"], p["value"]) if v > 0]
    ys += [o["y_hi"] for s in series for o in s["overlays"]]
    if not ys:
        return fig
    yr = [math.log10(min(ys)) - 0.15, math.log10(max(ys)) + 0.35]
    fig.update_xaxes(type="log", tickvals=[a for _k, a, _l in HORIZONS],
                     ticktext=[t(f"trigger_algo.fc.h.{k}", fr) for k, _a, fr in HORIZONS],
                     range=[math.log10(4.2), math.log10(5600)])
    fig.update_yaxes(type="log", range=yr,
                     title_text=t("trigger_algo.fc.axis", "Écoutes cumulées depuis la sortie"))
    fig.update_layout(height=470, margin=dict(t=30, r=60))
    return fig


def _alpha(hex_colour: str, a: float) -> str:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"


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


def _title_series(daily: pd.DataFrame, release, est: dict, rate: dict | None) -> dict | None:
    """One title's path, fit and overlays from its imported days. Pure."""
    from src.utils.algo_order import ALGO_ORDER
    hist = daily_by_age(daily, release)
    fit = fit_decay(hist)
    path = cumulative_path(hist, fit)
    if not path:
        return None
    return {"path": path, "fit": fit, "rate_info": rate,
            "rate": rate["eur_par_stream"] if rate else None,
            "overlays": algo_overlays(est, path, int(hist["age"].max()), ALGO_ORDER)}


def show_forecast(db, artist_id: int, picks: list[tuple]) -> None:
    """The picked releases' forecast on ONE figure (R584) — read here, drawn here (gold
    coverage). `picks`: (song, release date) pairs, the reference first."""
    import streamlit as st

    from src.dashboard.utils import charts
    from src.dashboard.utils.artist_cashflow import track_stream_rate

    from ._tab_algo_streams import load_estimates
    st.markdown(t("trigger_algo.fc.head_all",
                  "**🔮 Prévision — écoutes cumulées et revenus**"))
    est, series = load_estimates(), []
    for song, release in picks:
        daily = db.fetch_df(
            "SELECT day, streams FROM v_s4a_song_daily WHERE artist_id = %s AND song = %s "
            "ORDER BY day", (artist_id, song))
        s = _title_series(daily, release, est, track_stream_rate(db, artist_id, song))
        if s is None:
            st.caption(t("trigger_algo.fc.empty_one",
                         "{song} : aucune écoute importée, pas de prévision.").format(song=song))
            continue
        series.append({**s, "name": song,
                       "colour": TITLE_COLORS[len(series) % len(TITLE_COLORS)]})
    if not series:
        return
    charts.plotly_chart(forecast_figure(series), width="stretch")
    st.caption(" ".join(f"**{s['name']}** — " + _forecast_note(s["fit"], s["rate_info"],
                                                                s["overlays"])
                        for s in series))
