"""The arithmetic of « Tout mon funnel » — pure, so a test can hold it without Streamlit.

Type: Utility
Uses: pandas, src.dashboard.utils.i18n (t)
Triggers: views/meta_x_spotify.py
Persists in: nothing

R213 (2026-09-27). What one unit of each funnel step cost, the streams gained above the
pre-campaign level, and the engagement that moved beyond streams. Split out of the view
when it crossed 1 200 lines (`tests/test_a_file_only_gets_shorter.py`).
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.utils.i18n import t

# R213 (lot b) — the minimum baseline before a « streams gained » step is drawn. Fewer
# days before the campaign and the « normal » level is a guess, not a measure.
BASELINE_MIN_DAYS = 14
BASELINE_DAYS = 28


def streams_gained(daily: pd.DataFrame, d0, d1) -> dict | None:
    """Streams of the linked track during [d0, d1] minus its pre-campaign level.

    `daily` holds (date, streams) from `BASELINE_DAYS` before d0 to d1. Returns
    {gained, during, baseline_per_day, baseline_days, days} or None when the baseline has
    fewer than `BASELINE_MIN_DAYS` measured days — absent, never zero. Pure.
    """
    if daily is None or daily.empty:
        return None
    d = daily.copy()
    d['date'] = pd.to_datetime(d['date']).dt.date
    d['streams'] = pd.to_numeric(d['streams'], errors='coerce')
    before = d[(d['date'] < d0)].dropna(subset=['streams'])
    during = d[(d['date'] >= d0) & (d['date'] <= d1)].dropna(subset=['streams'])
    if len(before) < BASELINE_MIN_DAYS or during.empty:
        return None
    per_day = float(before['streams'].mean())
    days = len(during)
    total = float(during['streams'].sum())
    return {'gained': total - per_day * days, 'during': total,
            'baseline_per_day': per_day, 'baseline_days': len(before), 'days': days}


# ── Shazam → streams, with its delay (R235, 2026-09-27) ─────────────────────────────
MIN_PAIRED_DAYS = 14
MAX_LAG_DAYS = 7


def best_lag(master: pd.DataFrame, lead: str, follow: str) -> dict | None:
    """The lag (0-7 days) at which daily `lead` best precedes daily `follow`. Pure.

    Needs `MIN_PAIRED_DAYS` days where BOTH are measured, and both must MOVE: a flat
    series (a campaign spending the same every day) correlates with nothing, and that is
    the expected answer, not a failure. Returns {lag, corr, days} or None — a correlation
    on a handful of days is noise, so fewer days is « not enough », never a number.
    R234 generalised it from the Shazam case (code-critic: generalise, don't duplicate)."""
    if master is None or not {lead, follow} <= set(master.columns):
        return None
    d = master[["date", lead, follow]].copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.set_index("date").sort_index()
    for col in (lead, follow):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    best = None
    for lag in range(MAX_LAG_DAYS + 1):
        pair = pd.concat([d[lead], d[follow].shift(-lag, freq="D")],
                         axis=1, keys=["s", "t"]).dropna()
        if len(pair) < MIN_PAIRED_DAYS or pair["s"].std() == 0 or pair["t"].std() == 0:
            continue
        corr = float(pair["s"].corr(pair["t"]))
        if best is None or corr > best["corr"]:
            best = {"lag": lag, "corr": corr, "days": len(pair)}
    return best


def shazam_stream_lag(master: pd.DataFrame) -> dict | None:
    """The lag at which daily Shazams best precede daily streams (daily Apple export,
    migration 142)."""
    return best_lag(master, "apple_shazams", "streams")


# ── R246 (fiche 38) — the other effects of the ad days, beside the listeners ──────────
_AUDIENCE_FLOWS = (
    # (column, FR label, is it a LEVEL whose daily gain is shown)
    ("streams", "Streams / jour (moyenne 7 j)", False),
    ("saves", "Sauvegardes / jour (moyenne 7 j)", False),
    ("playlist_adds", "Ajouts en playlist / jour (moyenne 7 j)", False),
    ("followers_level", "Abonnés gagnés / jour (moyenne 7 j)", True),
)


def audience_flows(daily: pd.DataFrame) -> dict[str, tuple[str, pd.Series]]:
    """{column: (label, 7-day mean per day)} — every one a FLOW, never a cumul (fiche 38). Pure.

    The owner asked for streams, subscribers, playlist adds, saves and cumulative streams
    next to the listeners. The cumul is left out on purpose: drawn beside daily flows on
    one axis it reads as a quantity per day (MEMORY « jamais tracer un cumul comme un
    quotidien »). Subscribers are a LEVEL: what moves per day is their gain."""
    out = {}
    if daily is None or daily.empty:
        return out
    d = daily.copy()
    d["day"] = pd.to_datetime(d["day"])
    d = d.set_index("day").sort_index()
    full = pd.date_range(d.index.min(), d.index.max())
    for col, label, level in _AUDIENCE_FLOWS:
        if col not in d:
            continue
        s = pd.to_numeric(d[col], errors="coerce").reindex(full)
        if level:
            s = s.diff()
        out[col] = (t(f"campaign_funnel.flow_{col}", label), s.rolling(7, min_periods=4).mean())
    return out
