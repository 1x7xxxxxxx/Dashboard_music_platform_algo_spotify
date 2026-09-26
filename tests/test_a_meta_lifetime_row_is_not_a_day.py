"""A Meta lifetime row never enters a per-day total.

Type: Sub
Uses: the live `spotify_etl` schema (meta_insights_performance, meta_insights_performance_day,
      v_meta_campaign_daily, v_meta_daily), src/ + airflow/dags/ + tools/ read as AST
Depends on: tests/db_gate.py (the live half skips without Postgres)
Persists in: nothing — the synthetic tenant and its rows are deleted on exit

R180 (2026-09-26). The `plateforme × famille` matrix of `.claude/dev-docs/gold-coverage.md`
had one empty `un-cumul-pris-pour-un-quotidien` cell: Meta Ads. The defect is real and was
paid twice: `meta_insights_performance` holds, next to its per-day rows, LIFETIME rows of an
earlier collector (one per campaign, keyed by the campaign's start date). Summed as days,
the « Dépenses » tile showed 6 165,65 € for 3 087,82 € spent, and the PDF about 2x.

Two halves, because the defect has two doors:
- live: `v_meta_campaign_daily` must total exactly what `v_meta_daily` (built on the per-day
  table) totals, with a lifetime row present;
- static: no SQL literal SUMs the raw windowed table — a period total reads a gold view.

Class: `a-cumulative-counter-charted-as-a-daily-figure` (family `un-cumul-pris-pour-un-quotidien`).
"""
from __future__ import annotations

import ast
import datetime as dt
import re
import uuid
from pathlib import Path

import pytest

from tests.db_gate import requires_live_db

_ROOT = Path(__file__).resolve().parents[1]
_RAW_SUM = re.compile(r"\bSUM\s*\((?:(?!\bFROM\b).)*\bFROM\s+meta_insights_performance\b(?!_day)",
                      re.I | re.S)
_TOTALS = {
    "v_meta_campaign_daily": "SELECT COALESCE(SUM(spend), 0) FROM v_meta_campaign_daily "
                             "WHERE artist_id = %s",
    "v_meta_daily": "SELECT COALESCE(SUM(spend), 0) FROM v_meta_daily WHERE artist_id = %s",
}


def raw_window_sums(source: str) -> list[int]:
    """Lines of SQL literals that SUM the windowed Meta table directly. Docstrings excluded."""
    tree = ast.parse(source)
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and n.body and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)}
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs and _RAW_SUM.search(n.value)]


def disagreeing_totals(total, pairs) -> list[tuple[str, str]]:
    """Pairs of relations whose totals differ. Pure: `total(name)` returns a number."""
    return [(a, b) for a, b in pairs if total(a) != total(b)]


def _sources():
    for top in ("src", "airflow/dags", "tools"):
        yield from (_ROOT / top).rglob("*.py")


def test_no_sql_sums_the_windowed_meta_table() -> None:
    hits = [f"{p.relative_to(_ROOT)}:{line}" for p in _sources()
            for line in raw_window_sums(p.read_text(encoding="utf-8"))]
    assert not hits, (f"{hits} : SUM over `meta_insights_performance` adds lifetime rows to "
                      "days. Read `v_meta_campaign_daily` or `v_meta_daily`.")


@requires_live_db()
@pytest.mark.xdist_group("meta-lifetime")
def test_a_lifetime_row_does_not_enter_the_campaign_total() -> None:
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    slug = f"metalife-{uuid.uuid4().hex[:10]}"
    tenant = db.fetch_query("INSERT INTO saas_artists (name, slug, tier, active) "
                            "VALUES (%s, %s, 'free', FALSE) RETURNING id", (slug, slug))[0][0]
    try:
        today = dt.date.today()
        for i, spend in enumerate((10, 20, 30)):
            day = today - dt.timedelta(days=i + 1)
            for table, col in (("meta_insights_performance", "date_start"),
                               ("meta_insights_performance_day", "day_date")):
                db.execute_query(f"INSERT INTO {table} (artist_id, campaign_name, {col}, spend) "
                                 "VALUES (%s, 'c', %s, %s)", (tenant, day, spend))
        # The lifetime row: the campaign's whole spend, keyed by its start date.
        db.execute_query("INSERT INTO meta_insights_performance (artist_id, campaign_name, "
                         "date_start, spend) VALUES (%s, 'c', %s, 60)",
                         (tenant, today - dt.timedelta(days=30)))
        totals = {n: db.fetch_query(sql, (tenant,))[0][0] for n, sql in _TOTALS.items()}
        assert totals["v_meta_daily"] == 60, f"the per-day seed did not land: {totals}"
        assert not disagreeing_totals(totals.__getitem__,
                                      [("v_meta_campaign_daily", "v_meta_daily")]), totals
    finally:
        for table in ("meta_insights_performance", "meta_insights_performance_day"):
            db.execute_query(f"DELETE FROM {table} WHERE artist_id = %s", (tenant,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (tenant,))
        db.close()


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the pre-fix PDF read is caught; the per-day table, a COUNT, a gold view and
    a docstring are not; two totals that differ are named, equal ones are not."""
    defect = 'q = "SELECT SUM(spend) FROM meta_insights_performance WHERE artist_id = %s"\n'
    assert raw_window_sums(defect) == [1]
    for sound in ('q = "SELECT SUM(spend) FROM meta_insights_performance_day"\n',
                  'q = "SELECT COUNT(*) FROM meta_insights_performance"\n',
                  'q = "SELECT SUM(spend) FROM v_meta_campaign_daily"\n',
                  '"""SELECT SUM(spend) FROM meta_insights_performance"""\n'):
        assert raw_window_sums(sound) == [], sound
    assert disagreeing_totals({"a": 120, "b": 60}.__getitem__, [("a", "b")]) == [("a", "b")]
    assert disagreeing_totals({"a": 60, "b": 60}.__getitem__, [("a", "b")]) == []
