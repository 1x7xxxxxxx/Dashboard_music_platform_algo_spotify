"""Road to Algo — what a trigger brings, predicted and measured, on one figure (R560).

Type: Sub
Uses: streamlit, plotly, pandas
Reads: s4a_song_algo_outcomes (manual capture, Saisie S4A),
       machine_learning/models/v3/algo_stream_estimates.json

Owner's Y3 of 2026-10-13, fiches 129 and 48: « fusionne-le-moi avec la fiche 129 ;
Release Radar en premier, ensuite Discover Weekly et ensuite Radio ; en pointillé les
prédictions ; avec notre dernière release de façon automatique ». One panel per algorithm:
the cohort's usual 28-day streams at 1 month, 6 months and 1 year, DOTTED with its
P25–P75 band (a prediction), and this track's own 28-day readings as SOLID points at the
age they were taken (a fact). The window radio, the four tiles and the stacked bar of
fiche 48 are gone — the points are the same readings, placed where they can be compared.
"""
import textwrap
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.dashboard.utils import charts
from src.dashboard.utils.i18n import t
from src.dashboard.utils.platform_colors import ALGO_COLORS
from src.utils.algo_order import ALGO_NAMES, ALGO_ORDER
from src.utils.artist_name_filter import (
    ARTIST_NAME_LIKE as _ARTIST_FILTER,
)

# ⚠️ The one exception to `ALGO_ORDER` (ADR-033 §3): this figure reads in the order the
# playlists ACT after a release — Release Radar in the first days, then Discover Weekly,
# then Radio — because its x axis is the track's age. Derived, not written by hand.
TRIGGER_ORDER = ("RR",) + tuple(a for a in ALGO_ORDER if a != "RR")
#: Mid-point, in days, of each age bucket of the export (`ages_days`).
_AGE_DAYS = {"j28": 28, "m6": 182, "y1": 365}


def _show_tab_algo_streams(db, song, artist_id, release_date=None):
    """R570 — drawn in « Où en sont mes titres », once per picked release."""
    st.markdown(t("trigger_algo.algostreams_header",
                  "**📈 Ce qu'un déclenchement rapporte — {song}**").format(song=song or "—"))
    est = load_estimates()
    readings = pd.DataFrame()
    if song and "1x7xxxxxxx" not in song.lower():
        readings = _load_readings(db, artist_id, song, release_date)
    if not est.get("estimates") and readings.empty:
        st.info(t("trigger_algo.algostreams_empty",
                  "Aucune estimation ni saisie pour ce titre. Saisis les streams "
                  "DW/RR/Radio dans 📝 Saisie S4A."))
        return
    charts.plotly_chart(estimates_figure(est, readings), width="stretch")
    st.caption(t("trigger_algo.est_caption",
                 "Streams de la playlist sur 28 jours À CET ÂGE, pas un total cumulé — tirés "
                 "des {n} titres du jeu d'entraînement. Point plein = ta saisie « 28 jours ». "
                 "« Pas assez de titres » : moins de {m} titres déclenchés de cet âge."
                 ).format(n=est.get("rows", "?"), m=est.get("min_n", 10)))


def _load_readings(db, artist_id, song, release_date) -> pd.DataFrame:
    """age_days, DW, RADIO, RR — this track's 28-day readings, empty without a release."""
    df = db.fetch_df(
        """SELECT recorded_at, dw_streams, rr_streams, radio_streams
           FROM s4a_song_algo_outcomes
           WHERE artist_id = %s AND song = %s AND time_window = '28d' AND song NOT ILIKE %s
           ORDER BY recorded_at""",
        (artist_id, song, _ARTIST_FILTER),
    )
    return readings_by_age(df, release_date)


def readings_by_age(df, release_date) -> pd.DataFrame:
    """Pure: the readings placed at the track's age on the day they were taken."""
    if df is None or df.empty or release_date is None:
        return pd.DataFrame(columns=["age_days", *ALGO_ORDER])
    age = (pd.to_datetime(df["recorded_at"]) - pd.Timestamp(release_date)).dt.days
    out = pd.DataFrame({"age_days": age})
    for a in ALGO_ORDER:
        out[a] = pd.to_numeric(df[f"{a.lower()}_streams"], errors="coerce")
    return out[out["age_days"] >= 0].reset_index(drop=True)


# ── R247 (fiche 43) — what an algorithm usually brings once it has triggered ──────────
_ESTIMATES = (Path(__file__).resolve().parents[4]
              / "machine_learning" / "models" / "v3" / "algo_stream_estimates.json")
_AGE_LABELS = {"j28": "Le 1er mois", "m6": "Vers 6 mois", "y1": "Vers 1 an"}


def load_estimates() -> dict:
    """The exported estimates, or {} when the artefact is absent. Pure on the file.

    No `path=` parameter: the gold-coverage map cannot resolve a default argument at the
    call site, and filed this figure « indéterminée » instead of « hors base »."""
    import json
    try:
        return json.loads(_ESTIMATES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _x_max(ests: dict, readings: pd.DataFrame | None) -> int:
    """The last age with something to show — a refused age past it is not drawn (R570)."""
    ages = [_AGE_DAYS[k] for a in TRIGGER_ORDER for k, c in (ests.get(a.lower()) or {}).items()
            if not c.get("refused")]
    if readings is not None and not readings.empty:
        ages += [int(v) for v in readings["age_days"]]
    return max(ages, default=max(_AGE_DAYS.values()))


def _cohort_traces(fig, ages: dict, colour: str, col: int) -> None:
    """The P25–P75 band and the dotted median of one algorithm's triggered tracks."""
    kept = [(_AGE_DAYS[k], c) for k, c in ages.items() if not c.get("refused")]
    if not kept:
        return
    xs = [x for x, _ in kept]
    fig.add_trace(go.Scatter(
        x=xs + xs[::-1], y=[c["p75"] for _, c in kept] + [c["p25"] for _, c in kept][::-1],
        mode="lines", fill="toself", fillcolor=_alpha(colour, 0.15), line=dict(width=0),
        hoverinfo="skip", showlegend=col == 1, legendgroup="band",
        name=t("trigger_algo.est_band", "Bande P25–P75 = la moitié des titres déclenchés")),
        row=1, col=col)
    fig.add_trace(go.Scatter(
        x=xs, y=[c["p50"] for _, c in kept], mode="lines+markers+text",
        line=dict(color=colour, dash="dot", width=2), marker=dict(size=7, symbol="circle-open"),
        text=[f"{c['p50']:,.0f}".replace(",", " ") for _, c in kept],
        textposition="top center", cliponaxis=False, showlegend=col == 1,
        name=t("trigger_algo.est_pred", "Pointillé = médiane des titres déclenchés (P50)"),
        legendgroup="pred",
        hovertemplate=t("trigger_algo.est_hover",
                        "%{x} jours : %{y:,.0f} streams sur 28 j (médiane)<extra></extra>")),
        row=1, col=col)


def _reading_trace(fig, readings: pd.DataFrame | None, algo: str, colour: str, col: int) -> None:
    if readings is None or readings.empty:
        return
    r = readings[readings[algo].notna()]
    fig.add_trace(go.Scatter(
        x=r["age_days"], y=r[algo], mode="markers",
        marker=dict(color=colour, size=11, line=dict(color="white", width=1)),
        showlegend=col == 1, legendgroup="real",
        name=t("trigger_algo.est_real", "Ton titre — mesuré"),
        hovertemplate=t("trigger_algo.real_hover",
                        "à %{x} jours : %{y:,.0f} streams sur 28 j (ta saisie)<extra></extra>")),
        row=1, col=col)


def estimates_figure(est: dict, readings: pd.DataFrame | None = None):
    """One panel per algorithm in `TRIGGER_ORDER`, each on its OWN scale (Radio at 6 months
    runs to 22 490): the cohort median dotted over its P25–P75 band, and the track's
    readings as solid points. A refused age is WRITTEN, never drawn as a zero. R570 — the
    x axis stops at the last age with something to show."""
    ests = est.get("estimates") or {}
    x_max = _x_max(ests, readings)
    fig = make_subplots(rows=1, cols=len(TRIGGER_ORDER), horizontal_spacing=0.07,
                        subplot_titles=[ALGO_NAMES[a] for a in TRIGGER_ORDER])
    for col, algo in enumerate(TRIGGER_ORDER, start=1):
        ages = ests.get(algo.lower()) or {}
        _cohort_traces(fig, ages, ALGO_COLORS[algo], col)
        for k, c in ages.items():
            if c.get("refused") and _AGE_DAYS[k] <= x_max:
                fig.add_annotation(
                    x=_AGE_DAYS[k], y=0, row=1, col=col, yanchor="bottom", showarrow=False,
                    font=dict(size=10, color="#888"),
                    text="<br>".join(textwrap.wrap(
                        t("trigger_algo.est_refused", "pas assez de titres ({n})").format(n=c["n"]), 12)))
        _reading_trace(fig, readings, algo, ALGO_COLORS[algo], col)
    shown = {k: v for k, v in _AGE_LABELS.items() if _AGE_DAYS[k] <= x_max}
    fig.update_xaxes(tickvals=[_AGE_DAYS[k] for k in shown],
                     ticktext=[t(f"trigger_algo.est_age.{k}", v) for k, v in shown.items()],
                     range=[0, round(x_max * 1.18)])
    fig.update_yaxes(rangemode="tozero")
    fig.update_yaxes(title_text=t("trigger_algo.est_axis", "Streams de l'algorithme sur 28 jours"),
                     row=1, col=1)
    fig.update_layout(height=400, margin=dict(t=50))
    return fig


def _alpha(hex_colour: str, a: float) -> str:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"
