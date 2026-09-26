"""A displayed rate is recomputed from its counts — never rescaled, never averaged.

Type: Sub
Uses: the live `spotify_etl` schema (v_meta_creative_daily, v_meta_campaign_daily),
      src/dashboard/views/meta_creatives.py, trigger_algo/_common/_budget_roi.py
Depends on: tests/db_gate.py (the DB tests skip without a live Postgres)
Persists in: nothing — the synthetic tenant and its rows are deleted on exit

Meta's `ctr` field is already a percent. The Créatives page multiplied it by 100 a
second time AND averaged per-ad rates, so a 1-impression / 1-click ad weighed as much
as a 1 000-impression one: on `spotify_etl_review` (2026-09-26) 32 of 61 creatives
displayed above 100 % (max 1 111.42 %) while the ratio of sums peaks at 10.25 %.

The fixture is built so each wrong form gives a DIFFERENT number:
    ad A: 1 impression, 1 click (ctr 100)   ad B: 1 000 impressions, 10 clicks (ctr 1)
    right: 100 * 11 / 1001 = 1.10     x100 again: 109.89     mean of ratios: 50.5

Class: `a-rate-rescaled-or-averaged-instead-of-recomputed-from-its-counts`
(family `deux-surfaces-deux-nombres`).
"""
from __future__ import annotations

import ast
import datetime as dt
import pathlib
import re
import uuid

import pandas as pd
import pytest

from tests.db_gate import requires_live_db

ROOT = pathlib.Path(__file__).resolve().parents[1]
_EXPECTED = round(100 * 11 / 1001, 2)          # 1.10
_EXPECTED_LINK = 100 * 11 / 2001               # three days, one of them zero-click
_DAY = dt.date.today() - dt.timedelta(days=3)
_TRACK = "rate-guard-track"


# ── pure: the weekly resample derives CTR from the week's sums ─────────────────────

def _day_rows(start: dt.date, n: int) -> list[dict]:
    rows = []
    for i in range(n):
        imp, clk = (1, 1) if i == 0 else (1000, 10)
        rows.append({"date": pd.Timestamp(start + dt.timedelta(days=i)), "spend": 1.0,
                     "impressions": imp, "clicks": clk, "reach": imp, "conversions": 1})
    return rows


def test_the_weekly_timeline_ctr_is_a_ratio_of_the_weeks_sums() -> None:
    from src.dashboard.views.meta_creatives import _prepare_timeline

    monday = dt.date(2026, 1, 5)
    ts = pd.DataFrame(_day_rows(monday, 4) + _day_rows(monday + dt.timedelta(days=140), 4))
    out, _, weekly = _prepare_timeline(ts)
    assert weekly
    # The empty weeks in between are masked (NaN); the two measured weeks remain.
    measured = out.dropna(subset=["ctr"])["ctr"].tolist()
    # A mean of the four daily rates would give (100 + 1 + 1 + 1) / 4 = 25.75.
    assert measured == pytest.approx([100 * 31 / 3001] * 2), (
        f"weekly CTR {measured!r} is not 100*Σclicks/Σimpressions of each week")


# ── static: no reader of these views rescales or averages a stored `ctr` ────────────

_VIEWS = re.compile(r"v_meta_creative_daily|v_meta_campaign_daily")
_BAD = re.compile(r"AVG\(\s*(?:NULLIF\(\s*)?(?:\w+\.)?ctr\b|\bctr\)?\s*\*\s*100|\bctr_sum\b",
                  re.IGNORECASE)
_BAD_PANDAS = re.compile(r"\[\s*['\"](?:avg_)?ctr['\"]\s*\]\s*\*\s*100")


def offending_sites(files) -> list[str]:
    """`file:line` of a SQL literal on the Meta gold views that rescales/averages `ctr`,
    or of a pandas `['ctr'] * 100`. Pure: `files` is an iterable of (name, source)."""
    hits = []
    for name, src in files:
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if _VIEWS.search(node.value) and _BAD.search(node.value):
                    hits.append(f"{name}:{node.lineno}")
        for i, line in enumerate(src.splitlines(), 1):
            if _BAD_PANDAS.search(line):
                hits.append(f"{name}:{i}")
    return sorted(set(hits))


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    bad = [("a.py", 'Q = """SELECT AVG(ctr) * 100 FROM v_meta_creative_daily"""\n'),
           ("b.py", 'Q = """SELECT SUM(ctr_sum)/SUM(ctr_n) FROM v_meta_creative_daily"""\n'),
           ("c.py", 'Q = """SELECT AVG(NULLIF(ctr, 0)) FROM v_meta_campaign_daily"""\n'),
           ("d.py", "df['ctr'] = df['ctr'] * 100\n")]
    good = [("e.py", 'Q = """SELECT 100.0*SUM(clicks)/NULLIF(SUM(impressions),0) AS ctr '
                     'FROM v_meta_creative_daily"""\n'),
            ("f.py", 'Q = """SELECT AVG(frequency) FROM v_meta_creative_daily"""\n')]
    assert offending_sites(bad) == ["a.py:1", "b.py:1", "c.py:1", "d.py:1"]
    assert offending_sites(good) == []


def test_no_reader_rescales_or_averages_a_stored_ctr() -> None:
    files = [(str(p.relative_to(ROOT)), p.read_text(encoding="utf-8"))
             for p in (ROOT / "src").rglob("*.py")]
    assert offending_sites(files) == [], (
        "a stored Meta `ctr` (already a percent) is rescaled or averaged; recompute "
        "100*SUM(clicks)/NULLIF(SUM(impressions),0) instead")


# ── live: every surface returns 1.10 on the seeded creative ────────────────────────

@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


def _seed_creative(db, tenant: int, tag: str) -> None:
    camp, adset = f"rg-camp-{tag}", f"rg-adset-{tag}"
    db.execute_query("INSERT INTO meta_campaigns (campaign_id, campaign_name, artist_id) "
                     "VALUES (%s, %s, %s)", (camp, f"Campaign {tag}", tenant))
    db.execute_query("INSERT INTO meta_adsets (adset_id, campaign_id, artist_id, "
                     "optimization_goal) VALUES (%s, %s, %s, 'OFFSITE_CONVERSIONS')",
                     (adset, camp, tenant))
    for ad, imp, clk, ctr in (("A", 1, 1, 100.0), ("B", 1000, 10, 1.0)):
        ad_id = f"rg-ad-{ad}-{tag}"
        db.execute_query("INSERT INTO meta_ads (ad_id, adset_id, campaign_id, ad_name, "
                         "artist_id) VALUES (%s, %s, %s, 'Rate guard creative', %s)",
                         (ad_id, adset, camp, tenant))
        db.execute_query("INSERT INTO meta_insights (artist_id, ad_id, date, impressions, "
                         "clicks, spend, reach, frequency, ctr, conversions) "
                         "VALUES (%s, %s, %s, %s, %s, 5, %s, 1, %s, 1)",
                         (tenant, ad_id, _DAY, imp, clk, imp, ctr))


def _seed_campaign(db, tenant: int, tag: str) -> None:
    name = f"Lever campaign {tag}"
    # Day 3 has no click at all: `AVG(NULLIF(ctr, 0))` drops it, a ratio of sums does not.
    for i, (imp, clk, ctr) in enumerate(((1, 1, 100.0), (1000, 10, 1.0), (1000, 0, 0.0))):
        day = _DAY - dt.timedelta(days=i)
        db.execute_query("INSERT INTO meta_insights_performance (artist_id, campaign_name, "
                         "date_start, spend, impressions, reach, results, link_clicks, ctr) "
                         "VALUES (%s, %s, %s, 5, %s, %s, %s, %s, %s)",
                         (tenant, name, day, imp, imp, clk, clk, ctr))
        db.execute_query("INSERT INTO meta_insights_performance_day (artist_id, "
                         "campaign_name, day_date, spend, results, impressions, reach) "
                         "VALUES (%s, %s, %s, 5, %s, %s, %s)", (tenant, name, day, clk, imp, imp))
    db.execute_query("INSERT INTO campaign_track_mapping (campaign_name, track_name, artist_id) "
                     "VALUES (%s, %s, %s)", (name, _TRACK, tenant))


@pytest.fixture
def tenant(db):
    tag = uuid.uuid4().hex[:10]
    tid = db.fetch_query("INSERT INTO saas_artists (name, slug, tier, active) "
                         "VALUES (%s, %s, 'free', FALSE) RETURNING id",
                         (f"rate-{tag}", f"rate-{tag}"))[0][0]
    try:
        _seed_creative(db, tid, tag)
        _seed_campaign(db, tid, tag)
        yield tid
    finally:
        for table in ("meta_insights", "meta_ads", "meta_adsets", "meta_campaigns",
                      "meta_insights_performance", "meta_insights_performance_day",
                      "campaign_track_mapping"):
            db.execute_query(f"DELETE FROM {table} WHERE artist_id = %s", (tid,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (tid,))


@pytest.mark.xdist_group("rate-from-counts")
@requires_live_db()
class TestLive:
    def test_the_ranking_ctr_is_the_ratio_of_summed_counts(self, db, tenant) -> None:
        from src.dashboard.views.meta_creatives import _QUERY_CREATIVES
        df = db.fetch_df(_QUERY_CREATIVES.format(acct=""), (tenant,))
        assert len(df) == 1
        assert float(df["avg_ctr"].iloc[0]) == _EXPECTED, (
            f"ranking avg_ctr {df['avg_ctr'].iloc[0]!r} != {_EXPECTED} "
            "(109.89 = rescaled twice, 50.5 = mean of per-ad rates)")

    def test_the_timeline_ctr_is_the_ratio_of_summed_counts(self, db, tenant) -> None:
        from src.dashboard.views.meta_creatives import _QUERY_TIMELINE, _prepare_timeline
        ts = db.fetch_df(_QUERY_TIMELINE.format(acct="", campaign_clause=""),
                         (tenant, "Rate guard creative"))
        ts["date"] = pd.to_datetime(ts["date"])
        out, _, _ = _prepare_timeline(ts)
        assert round(float(out["ctr"].iloc[0]), 2) == _EXPECTED, (
            f"timeline ctr {out['ctr'].iloc[0]!r} != {_EXPECTED}")

    def test_the_fatigue_ctr_is_the_ratio_of_summed_counts(self, db, tenant) -> None:
        from src.dashboard.views.meta_creatives import _QUERY_FATIGUE
        ts = db.fetch_df(_QUERY_FATIGUE.format(acct=""), (tenant, "Rate guard creative"))
        assert float(ts["ctr"].iloc[0]) == _EXPECTED, (
            f"fatigue ctr {ts['ctr'].iloc[0]!r} != {_EXPECTED}")

    def test_the_lever_link_ctr_counts_the_zero_click_day(self, db, tenant) -> None:
        from src.dashboard.views.trigger_algo._common._budget_roi import _META_LEVER_QUERY
        df = db.fetch_df(_META_LEVER_QUERY, (tenant, tenant, tenant, _TRACK))
        assert len(df) == 1
        assert float(df["ctr"].iloc[0]) == pytest.approx(_EXPECTED_LINK), (
            f"lever ctr {df['ctr'].iloc[0]!r} != 100*11/2001 "
            "(50.5 = mean of non-zero daily rates)")

    def test_no_displayed_ctr_exceeds_100_on_the_real_base(self, db) -> None:
        from src.dashboard.views.meta_creatives import _QUERY_CREATIVES, _QUERY_FATIGUE
        over = []
        pairs = db.fetch_query("SELECT DISTINCT artist_id, creative_name "
                               "FROM v_meta_creative_daily WHERE creative_name IS NOT NULL")
        for artist in {a for a, _ in pairs}:
            df = db.fetch_df(_QUERY_CREATIVES.format(acct=""), (artist,))
            over += [(artist, n) for n, v in zip(df["creative_name"], df["avg_ctr"])
                     if v is not None and float(v) > 100]
        for artist, creative in pairs:
            ts = db.fetch_df(_QUERY_FATIGUE.format(acct=""), (artist, creative))
            over += [(artist, creative, "fatigue") for v in ts["ctr"]
                     if v is not None and float(v) > 100]
        assert over == [], f"{len(over)} displayed CTR above 100 %: {over[:5]}"
