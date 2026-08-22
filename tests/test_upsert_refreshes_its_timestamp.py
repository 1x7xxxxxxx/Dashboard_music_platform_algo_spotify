"""An upsert that refreshes a row must refresh the row's clock too.

Installed 2026-08-22. `_meta_upsert` wrote `update_columns` lists that did not
include `collected_at`, so every nightly re-collection updated the data and left the
timestamp at its first-ever value.

Measured that morning: `pg_stat_user_tables` reported **17 545 UPDATE and 0 INSERT on
`meta_insights`**, while `MAX(collected_at)` still said 29 May. Anything reading that
column — a "last updated" caption, a freshness probe, a CSV export header — was three
months wrong.

Exactly one table already carried it, `meta_insights_performance_day`, and that is
also the only Meta table `freshness_monitor` watches. The monitor happened to be
pointed at the one clock that moved, which is why nothing ever alerted about it. That
coincidence is the reason this file checks the SHAPE across every table rather than
re-checking the three that were wrong.
"""
from __future__ import annotations

import uuid

import pytest

from tests.db_gate import requires_live_db


# ── the shape, on every table the collector writes ───────────────────────────

def test_every_meta_upsert_refreshes_collected_at():
    from src.collectors._meta_upsert import _MetaUpsertMixin

    insight_cols, _conflict = _MetaUpsertMixin._insight_upsert_maps()
    assert insight_cols, "no insight tables found — the map is not being read"

    missing = sorted(t for t, cols in insight_cols.items()
                     if "collected_at" not in cols)
    assert not missing, (
        f"{len(missing)} insight table(s) refresh their rows without refreshing "
        f"`collected_at`: {missing[:5]}{'…' if len(missing) > 5 else ''}. "
        "The row moves and its clock does not, so every reader of MAX(collected_at) "
        "reports the date of the FIRST collection, forever."
    )


def test_the_config_tables_refresh_it_too():
    """campaigns / adsets / ads are upserted from literals, not from the map."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "src/collectors/_meta_upsert.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    offenders = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "upsert_many"):
            continue
        table = node.args[0].value if node.args and isinstance(
            node.args[0], ast.Constant) else "<dynamic>"
        upd = next((k.value for k in node.keywords if k.arg == "update_columns"), None)
        if not isinstance(upd, ast.List):        # built from the map — covered above
            continue
        names = {e.value for e in upd.elts if isinstance(e, ast.Constant)}
        if "collected_at" not in names:
            offenders.append(f"{table} (line {node.lineno})")

    assert not offenders, (
        f"literal upserts that do not refresh collected_at: {offenders}"
    )


# ── behavioural, against the real database ───────────────────────────────────

class TestAgainstPostgres:
    pytestmark = requires_live_db()

    def test_a_second_upsert_moves_the_timestamp(self):
        """The property, end to end: update the same row twice, the clock moves."""
        from datetime import datetime, timedelta, timezone

        from src.dashboard.utils import get_db_connection

        db = get_db_connection()
        slug = f"upsert-{uuid.uuid4().hex[:10]}"
        artist_id = db.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active) "
            "VALUES (%s, %s, 'free', TRUE) RETURNING id", (slug, slug))[0][0]
        campaign_id = f"c-{uuid.uuid4().hex[:12]}"
        old = datetime.now(timezone.utc) - timedelta(days=90)
        try:
            row = {
                "artist_id": artist_id, "campaign_id": campaign_id,
                "campaign_name": "avant", "status": "PAUSED",
                "collected_at": old,
            }
            db.upsert_many("meta_campaigns", [row],
                           conflict_columns=["campaign_id"],
                           update_columns=["campaign_name", "status", "collected_at"])
            first = db.fetch_query(
                "SELECT collected_at FROM meta_campaigns WHERE campaign_id = %s",
                (campaign_id,))[0][0]

            row["campaign_name"] = "après"
            row["collected_at"] = datetime.now(timezone.utc)
            db.upsert_many("meta_campaigns", [row],
                           conflict_columns=["campaign_id"],
                           update_columns=["campaign_name", "status", "collected_at"])
            second, name = db.fetch_query(
                "SELECT collected_at, campaign_name FROM meta_campaigns "
                "WHERE campaign_id = %s", (campaign_id,))[0]

            assert name == "après", "the data itself did not update — test is vacuous"
            assert second > first, (
                f"the row was refreshed and its clock was not: {first} → {second}. "
                "That is the 90-day-stale reading with fresh data underneath."
            )
        finally:
            db.execute_query("DELETE FROM meta_campaigns WHERE campaign_id = %s",
                             (campaign_id,))
            db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
            db.close()

    def test_leaving_it_out_freezes_the_clock(self):
        """The inverse, so the assertion above is not true of any upsert at all."""
        from datetime import datetime, timedelta, timezone

        from src.dashboard.utils import get_db_connection

        db = get_db_connection()
        slug = f"frozen-{uuid.uuid4().hex[:10]}"
        artist_id = db.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active) "
            "VALUES (%s, %s, 'free', TRUE) RETURNING id", (slug, slug))[0][0]
        campaign_id = f"c-{uuid.uuid4().hex[:12]}"
        old = datetime.now(timezone.utc) - timedelta(days=90)
        try:
            row = {"artist_id": artist_id, "campaign_id": campaign_id,
                   "campaign_name": "avant", "status": "PAUSED", "collected_at": old}
            db.upsert_many("meta_campaigns", [row], conflict_columns=["campaign_id"],
                           update_columns=["campaign_name", "collected_at"])
            row["campaign_name"] = "après"
            row["collected_at"] = datetime.now(timezone.utc)
            # collected_at deliberately absent from update_columns — the old behaviour
            db.upsert_many("meta_campaigns", [row], conflict_columns=["campaign_id"],
                           update_columns=["campaign_name"])
            ts, name = db.fetch_query(
                "SELECT collected_at, campaign_name FROM meta_campaigns "
                "WHERE campaign_id = %s", (campaign_id,))[0]
            assert name == "après"
            assert (datetime.now(timezone.utc) - ts.replace(
                tzinfo=ts.tzinfo or timezone.utc)).days >= 89, (
                "omitting the column no longer freezes the clock — then the fix above "
                "is not what makes the difference, and this file measures nothing"
            )
        finally:
            db.execute_query("DELETE FROM meta_campaigns WHERE campaign_id = %s",
                             (campaign_id,))
            db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
            db.close()
