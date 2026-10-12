"""« Restant estimé » is lifetime budget minus LIFETIME spend, not minus the window (R526).

Type: Guard
Uses: src.dashboard.views.trigger_algo._common._budget_roi
Depends on: live Postgres for the SQL test (skipped without it)
Persists in: nothing (the seeded rows are rolled back)

The defect (code-critic a posteriori of R404, 2026-10-12): `_tab_budget_roi` computed
`max(lifetime_budget - spend_of_the_selected_window, 0)`. On a 60-day campaign at
10 €/day with a 1 000 € lifetime budget, a 7-day window showed 930 € left when 400 €
were; and `max(…, 0)` turned an overspend into « 0 € restant ». The pacing planner
beside it proposed the whole lifetime budget as « Budget à étaler ».
"""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pytest

from src.dashboard.views.trigger_algo._common._budget_roi import (
    ACTIVE_LIFETIME_SPEND_SQL,
    remaining_lifetime_budget,
)

_ROOT = Path(__file__).resolve().parents[1]
_TAB = _ROOT / "src" / "dashboard" / "views" / "trigger_algo" / "_tab_budget_roi.py"


def test_an_overspend_is_negative_not_clamped_to_zero() -> None:
    assert remaining_lifetime_budget(1000.0, 600.0) == 400.0
    assert remaining_lifetime_budget(100.0, 130.0) == -30.0


def test_the_tab_derives_the_remainder_from_the_shared_helper() -> None:
    """The window-spend subtraction must not come back inline."""
    tree = ast.parse(_TAB.read_text(encoding="utf-8"))
    calls = {getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "remaining_lifetime_budget" in calls
    inline = [n.lineno for n in ast.walk(tree)
              if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub)
              and getattr(n.left, "id", None) == "lifetime_budget"]
    assert not inline, f"_tab_budget_roi.py:{inline} subtracts from lifetime_budget inline"


def _dsn():
    from tests.db_gate import dsn

    return dsn()


@pytest.mark.skipif(_dsn() is None, reason="No Postgres — the SQL needs the live views")
def test_lifetime_spend_counts_every_day_of_active_campaigns_only() -> None:
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT min(id) FROM saas_artists")
            (artist,) = cur.fetchone()
            if artist is None:
                pytest.skip("no tenant to seed")
            sql = ACTIVE_LIFETIME_SPEND_SQL + " WHERE d.artist_id = %s"
            cur.execute(sql, (artist,))
            before = float(cur.fetchone()[0])

            today = dt.date.today()
            for cid, status in (("r526-active", "ACTIVE"), ("r526-paused", "PAUSED")):
                cur.execute(
                    "INSERT INTO meta_campaigns (campaign_id, campaign_name, artist_id, "
                    "status, lifetime_budget, ad_account_id) VALUES (%s,%s,%s,%s,1000,NULL)",
                    (cid, cid, artist, status))
                for k in range(60):
                    cur.execute(
                        "INSERT INTO meta_insights_performance_day (campaign_name, day_date, "
                        "spend, artist_id, ad_account_id) VALUES (%s,%s,10,%s,NULL)",
                        (cid, today - dt.timedelta(days=k), artist))
            cur.execute(sql, (artist,))
            after = float(cur.fetchone()[0])
    finally:
        conn.rollback()
        conn.close()

    # 60 days × 10 € of the ACTIVE campaign; the paused one's 600 € are not counted.
    assert after - before == pytest.approx(600.0)
    assert remaining_lifetime_budget(1000.0, after - before) == pytest.approx(400.0)
