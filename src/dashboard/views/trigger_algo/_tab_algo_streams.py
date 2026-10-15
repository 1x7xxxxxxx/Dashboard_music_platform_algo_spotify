"""Road to Algo — what a trigger brings: the cohort's estimates and the title's readings.

Type: Sub
Uses: plotly, pandas
Reads: s4a_song_algo_outcomes (manual capture, Saisie S4A), tracks (release date),
       machine_learning/models/v3/algo_stream_estimates.json
Triggers: views/trigger_algo/_release_targets.py (the mini chart beside each playlist),
          views/trigger_algo/_tab_catalogue.py, views/trigger_algo/_forecast.py
Persists in: nothing

R560 drew one figure per release, one panel per algorithm: the cohort's usual 28-day
streams at 1 month, 6 months and 1 year, DOTTED over its P25–P75 band (a prediction),
and the title's own 28-day readings as SOLID points at the age they were taken (a fact).
R583 (owner, 2026-10-15) moved it beside each playlist in « Où en sont mes titres »,
next to the gauge — one chronological view per playlist, and no separate section.
"""
import textwrap
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.utils.i18n import t
from src.dashboard.utils.platform_colors import ALGO_COLORS
from src.utils.algo_order import ALGO_ORDER
from src.utils.artist_name_filter import (
    ARTIST_NAME_LIKE as _ARTIST_FILTER,
)

# ⚠️ The one exception to `ALGO_ORDER` (ADR-033 §3): this figure reads in the order the
# playlists ACT after a release — Release Radar in the first days, then Discover Weekly,
# then Radio — because its x axis is the track's age. Derived, not written by hand.
TRIGGER_ORDER = ("RR",) + tuple(a for a in ALGO_ORDER if a != "RR")
#: Mid-point, in days, of each age bucket of the export (`ages_days`).
_AGE_DAYS = {"j28": 28, "m6": 182, "y1": 365}


def release_date(db, artist_id, song: str):
    """The track's release date (None when unknown) — `tracks` is scoped by saas_artist_id."""
    import streamlit as st

    from src.utils.track_matching import canonical_song_sql
    try:
        rows = db.fetch_query(
            f"SELECT release_date FROM tracks WHERE {canonical_song_sql('track_name')} = %s "
            "AND saas_artist_id = %s LIMIT 1", (song, artist_id))
    except Exception as e:                           # noqa: BLE001 — said, not hidden (R525)
        st.caption(t("trigger_algo.release_date_unreadable",
                     "Date de sortie illisible ({err}) — la prévision part du premier "
                     "jour importé.").format(err=type(e).__name__))
        return None
    return rows[0][0] if rows and rows[0][0] else None


def load_readings(db, artist_id, song, release_date) -> pd.DataFrame:
    """age_days, DW, RADIO, RR — this track's 28-day readings, empty without a release."""
    if not song or "1x7xxxxxxx" in song.lower():
        return readings_by_age(None, None)
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


def cohort_traces(fig, ages: dict, colour: str, *, row: int, col: int, first: bool) -> None:
    """The P25–P75 band and the dotted median of one algorithm's triggered tracks."""
    kept = [(_AGE_DAYS[k], c) for k, c in ages.items() if not c.get("refused")]
    if not kept:
        return
    xs = [x for x, _ in kept]
    fig.add_trace(go.Scatter(
        x=xs + xs[::-1], y=[c["p75"] for _, c in kept] + [c["p25"] for _, c in kept][::-1],
        mode="lines", fill="toself", fillcolor=_alpha(colour, 0.15), line=dict(width=0),
        hoverinfo="skip", showlegend=first, legendgroup="band",
        name=t("trigger_algo.est_band", "Bande P25–P75 = la moitié des titres déclenchés")),
        row=row, col=col)
    fig.add_trace(go.Scatter(
        x=xs, y=[c["p50"] for _, c in kept], mode="lines+markers+text",
        line=dict(color=colour, dash="dot", width=2), marker=dict(size=7, symbol="circle-open"),
        text=[f"{c['p50']:,.0f}".replace(",", " ") for _, c in kept],
        textposition="top center", cliponaxis=False, showlegend=first,
        name=t("trigger_algo.est_pred", "Pointillé = médiane des titres déclenchés (P50)"),
        legendgroup="pred",
        hovertemplate=t("trigger_algo.est_hover",
                        "%{x} jours : %{y:,.0f} streams sur 28 j (médiane)<extra></extra>")),
        row=row, col=col)


def reading_trace(fig, readings: pd.DataFrame | None, algo: str, *, song: str, symbol: str,
                  row: int, col: int, first: bool) -> None:
    """One title's 28-day readings of `algo`, solid points at the age they were taken."""
    if readings is None or readings.empty:
        return
    r = readings[readings[algo].notna()]
    fig.add_trace(go.Scatter(
        x=r["age_days"], y=r[algo], mode="markers",
        marker=dict(color=ALGO_COLORS[algo], size=11, symbol=symbol,
                    line=dict(color="white", width=1)),
        showlegend=first, legendgroup=f"real-{song}",
        name=t("trigger_algo.est_real_song", "{song} — mesuré").format(song=song),
        hovertemplate=song + " · " + t(
            "trigger_algo.real_hover",
            "à %{x} jours : %{y:,.0f} streams sur 28 j (ta saisie)<extra></extra>")),
        row=row, col=col)


def x_max(ests: dict, readings: list) -> int:
    """The last age with something to show — a refused age past it is not drawn (R570)."""
    ages = [_AGE_DAYS[k] for a in TRIGGER_ORDER for k, c in (ests.get(a.lower()) or {}).items()
            if not c.get("refused")]
    for r in readings:
        if r is not None and not r.empty:
            ages += [int(v) for v in r["age_days"]]
    return max(ages, default=max(_AGE_DAYS.values()))


def refused_notes(fig, ages: dict, limit: int, *, row: int, col: int) -> None:
    """A refused age is WRITTEN, never drawn as a zero."""
    for k, c in ages.items():
        if c.get("refused") and _AGE_DAYS[k] <= limit:
            fig.add_annotation(
                x=_AGE_DAYS[k], y=0, row=row, col=col, yanchor="bottom", showarrow=False,
                font=dict(size=9, color="#888"),
                text="<br>".join(textwrap.wrap(
                    t("trigger_algo.est_refused", "pas assez de titres ({n})").format(n=c["n"]),
                    12)))


def age_ticks(limit: int) -> tuple[list, list]:
    shown = {k: v for k, v in _AGE_LABELS.items() if _AGE_DAYS[k] <= limit}
    return ([_AGE_DAYS[k] for k in shown],
            [t(f"trigger_algo.est_age.{k}", v) for k, v in shown.items()])


def _alpha(hex_colour: str, a: float) -> str:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"
