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


# R213 (lot d) — engagement during the campaign against the days before it. FLOWS are
# counted per day (a mean); LEVELS (followers) are a stock, so what compares is their GAIN
# per day. `v_s4a_audience_daily` is artist-level, daily since 2024-01-01 (migration 117).
ENGAGEMENT = (
    ("listeners",       "Auditeurs / jour",          "flow"),
    ("saves",           "Sauvegardes / jour",        "flow"),
    ("playlist_adds",   "Ajouts en playlist / jour", "flow"),
    ("followers_level", "Abonnés Spotify gagnés / jour", "level"),
    ("ig_followers",    "Abonnés Instagram gagnés / jour", "level"),
)


def per_day(serie: pd.Series, kind: str) -> float | None:
    """Mean of a flow, or the gain per day of a level — None when unmeasured. Pure."""
    s = pd.to_numeric(serie, errors='coerce').dropna()
    if kind == "flow":
        return float(s.mean()) if len(s) else None
    return float((s.iloc[-1] - s.iloc[0]) / (len(s) - 1)) if len(s) >= 2 else None


def engagement_lift(df: pd.DataFrame, d0, d1) -> list[dict]:
    """One row per engagement measure: before / during per day and the change. Pure.

    A measure enters only with `BASELINE_MIN_DAYS` measured days before d0 and at least
    one during; otherwise it is absent — the table says « non mesuré », never 0."""
    out = []
    if df is None or df.empty:
        return out
    d = df.copy()
    d['date'] = pd.to_datetime(d['date']).dt.date
    # SORTED: a level's gain is last − first IN TIME; the test caught it read in row order.
    d = d.sort_values('date')
    before, during = d[d['date'] < d0], d[(d['date'] >= d0) & (d['date'] <= d1)]
    for col, label, kind in ENGAGEMENT:
        if col not in d.columns:
            continue
        n_before = pd.to_numeric(before[col], errors='coerce').notna().sum()
        b = per_day(before[col], kind) if n_before >= BASELINE_MIN_DAYS else None
        w = per_day(during[col], kind)
        change = (100 * (w - b) / abs(b)) if (b not in (None, 0) and w is not None) else None
        out.append({'col': col, 'label': label, 'before': b, 'during': w, 'change': change})
    return out


def step_texts(values: list[float], spend: float | None) -> list[str]:
    """« 1 234 · 12 % de l'étape d'avant · 0,05 €/unité » for each funnel step. Pure.

    The cost is spend ÷ the step's volume, i.e. what one unit of THAT step cost; the
    first step (impressions) is priced per thousand, as Meta prices it."""
    out = []
    for i, v in enumerate(values):
        parts = [f"{v:,.0f}".replace(",", " ")]
        if i > 0 and values[i - 1]:
            parts.append(t("meta_x_spotify.f_kept", "{p} % de l'étape d'avant").format(
                p=f"{100 * v / values[i - 1]:.1f}".replace(".", ",")))
        if spend and v > 0:
            unit = spend / v * (1000 if i == 0 else 1)
            label = (t("meta_x_spotify.f_cpm", "{c} € les 1 000") if i == 0
                     else t("meta_x_spotify.f_cost", "{c} € l'unité"))
            parts.append(label.format(c=f"{unit:,.3f}".replace(",", " ").replace(".", ",")))
        out.append(" · ".join(parts))
    return out
