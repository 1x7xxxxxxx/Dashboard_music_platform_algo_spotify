"""The arithmetic of « Tout mon funnel » — pure, so a test can hold it without Streamlit.

Type: Utility
Uses: pandas, src.dashboard.utils.i18n (t)
Triggers: views/meta_x_spotify.py, views/meta_creatives.py (funnel_stages)
Persists in: nothing

R213 (2026-09-27). What one unit of each funnel step cost, the streams gained above the
pre-campaign level, and the engagement that moved beyond streams. Split out of the view
when it crossed 1 200 lines (`tests/test_a_file_only_gets_shorter.py`).
"""
from __future__ import annotations

import pandas as pd

from src.dashboard.utils.date_format import format_date
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


# ── One creative's funnel (moved from views/meta_creatives.py, R209 2026-09-27) ──

def _measured_sum(rows: pd.DataFrame, col: str) -> int | None:
    """The column's sum over `rows`, or None when ANY row did not measure it."""
    if col not in rows or rows.empty:
        return None
    vals = pd.to_numeric(rows[col], errors='coerce')
    if vals.isna().any():
        return None
    return int(vals.sum())


def funnel_stages(rows: pd.DataFrame) -> list[tuple[str, str, int]]:
    """(i18n key, default label, value) for each MEASURED stage of one creative's funnel.

    `rows` = every (creative, campaign) row of ONE creative name; they are summed, so a
    creative run in two campaigns shows both (the old `.iloc[0]` showed one campaign's
    funnel under the bare creative name).

    Measured 2026-09-26 on spotify_etl_review, artist 1: the funnel drew
    impressions → `clicks` → `conversions` as « Clics sortants ». `clicks` is Meta
    clicks (all) and `conversions` is the ad set goal's result — the Hypeddit outbound
    event counted twice, or a VIDEO VIEW under THRUPLAY. 18 of 61 creative rows widened
    (2 732 → 48 → 60 ; 2 028 → 7 → 1 670 under THRUPLAY).

    The stages are now the three that nest by construction:
      impressions → link clicks (`inline_link_clicks`) → outbound clicks
      (`custom_conversions`, the offsite_conversion.custom family — whatever the goal).
    The goal's `total_results` is never a stage. Until the ad grain is re-collected
    (migration 138), link clicks are unmeasured; stage 2 then falls back to clicks (all)
    UNDER THAT NAME. A zero or unmeasured stage is dropped, never drawn at 0.
    """
    imp = _measured_sum(rows, 'total_impressions')
    link = _measured_sum(rows, 'total_link_clicks')
    out = _measured_sum(rows, 'total_outbound')
    stages: list[tuple[str, str, int]] = []
    if imp:
        stages.append(("meta_creatives.impressions", "Impressions", imp))
    if link:
        stages.append(("meta_creatives.link_clicks", "Clics sur le lien", link))
    else:
        clk = _measured_sum(rows, 'total_clicks')
        if clk:
            stages.append(("meta_creatives.clicks_all", "Clics (tous types)", clk))
    if out:
        stages.append(("meta_creatives.results", "Clics sortants", out))
    return stages


# ── Shazam → streams, with its delay (R235, 2026-09-27) ─────────────────────────────
MIN_PAIRED_DAYS = 14
MAX_LAG_DAYS = 7


def shazam_stream_lag(master: pd.DataFrame) -> dict | None:
    """The lag (0-7 days) at which daily Shazams best precede daily streams. Pure.

    Needs `MIN_PAIRED_DAYS` days where BOTH are measured — a daily Apple export during
    the campaign (migration 142). Returns {lag, corr, days} or None; a correlation on a
    handful of days is noise, so fewer days is « not enough », never a number."""
    if master is None or not {"apple_shazams", "streams"} <= set(master.columns):
        return None
    d = master[["date", "apple_shazams", "streams"]].copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.set_index("date").sort_index()
    best = None
    for lag in range(MAX_LAG_DAYS + 1):
        pair = pd.concat([d["apple_shazams"], d["streams"].shift(-lag, freq="D")],
                         axis=1, keys=["s", "t"]).dropna()
        if len(pair) < MIN_PAIRED_DAYS or pair["s"].std() == 0 or pair["t"].std() == 0:
            continue
        corr = float(pair["s"].corr(pair["t"]))
        if best is None or corr > best["corr"]:
            best = {"lag": lag, "corr": corr, "days": len(pair)}
    return best


# ── The money around a campaign (moved from views/meta_x_spotify.py, R235) ─────────
def campaign_treasury(db, artist_id, d0, d1, spend: float | None) -> str:
    """R213 (lot f) — the money around this campaign, from the ONE money door.

    Revenue is monthly and a campaign is counted in days, so the sentence speaks of the
    WHOLE months the window touches — `get_roi_data` widens it and says so, and it is the
    same definition the treasury (R212) draws. Revenue is never attributed to the
    campaign: royalties of those months come from every track, and they arrive months
    after the streams."""
    from src.dashboard.utils.kpi_helpers import get_roi_data

    def fmt_eur(v):
        # The page writes euros the French way (« 1 463,61 € »), like its other captions.
        return "—" if v is None else f"{v:,.2f} €".replace(",", " ").replace(".", ",")

    roi = get_roi_data(db, artist_id, d0, d1)
    if roi['revenue_eur'] is None and roi['total_spend'] is None:
        return ""
    return " " + t("meta_x_spotify.funnel_treasury",
                   "💶 Sur les mois de cette campagne ({a} → {b}) : **{rev}** de revenus "
                   "nets (tous titres, versés avec retard), **{tot}** de dépenses au total, "
                   "dont **{sp}** pour cette campagne sur la fenêtre.").format(
        a=format_date(roi['effective_from']), b=format_date(roi['effective_to']),
        rev=fmt_eur(roi['revenue_eur']), tot=fmt_eur(roi['total_spend']),
        sp=fmt_eur(spend))
