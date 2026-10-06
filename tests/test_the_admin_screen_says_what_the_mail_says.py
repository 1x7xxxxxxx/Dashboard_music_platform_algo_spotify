"""R418 — the admin « Collecte par artiste » screen says what the evening mail says.

Type: Sub
Uses: src.utils.collection_outcomes (collection_failures), airflow/dags/alert_monitor.py
      (check_collection_outcomes, executed from its source), src.dashboard.views.admin_collection
      (readiness_snapshot), src.utils.artist_readiness
Depends on: a live Postgres for the readiness half (requires_live_db)
Persists in: nothing — every tenant it creates is deleted

The owner deletes the mail, so « 🔴 NE COLLECTE PAS » must be readable in the admin view.
A second query written for the screen would drift from the mail's; both surfaces must
therefore return the SAME rows for the same database — that is what is tested here, by
running the DAG task's own code and the screen's own function on one input.
"""
from __future__ import annotations

import ast
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.db_gate import requires_live_db

REPO = Path(__file__).resolve().parents[1]
DAG = REPO / "airflow" / "dags" / "alert_monitor.py"
_T = datetime(2026, 10, 5, 3, 0)


class _FakeLedger:
    """A db whose ledger query answers `rows` — or raises, when rows is an exception."""

    def __init__(self, rows):
        self.rows = rows

    def fetch_query(self, sql, params=None):
        if isinstance(self.rows, Exception):
            raise self.rows
        assert "etl_run_log" in sql
        return self.rows

    def close(self):
        pass


_ROWS = [
    (12, "Benken", "meta", "meta_ads_daily", "failed", "(#200) not granted", _T, None, 93),
    (14, "GRiNCH", "soundcloud", "soundcloud_daily", "partial", None, _T, _T - timedelta(days=2), 1),
    (15, "Ok", "youtube", "youtube_daily", "success", None, _T, _T, 0),
]


def _dag_task(db) -> list:
    """Run `check_collection_outcomes` from the DAG's SOURCE — the module needs Airflow."""
    tree = ast.parse(DAG.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "check_collection_outcomes")
    ns = {"logger": logging.getLogger("dag"), "safe_error": lambda e: type(e).__name__}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(DAG), "exec"), ns)  # noqa: S102
    pushed = {}

    class _TI:
        def xcom_push(self, key, value):
            pushed[key] = value

    import src.database.postgres_handler as ph
    real = ph.PostgresHandler.from_env_or_config
    ph.PostgresHandler.from_env_or_config = staticmethod(lambda: db)
    try:
        ns["check_collection_outcomes"](task_instance=_TI())
    finally:
        ph.PostgresHandler.from_env_or_config = real
    return pushed["collection_failures"]


def test_the_mail_and_the_screen_read_the_same_failures() -> None:
    from src.utils.collection_outcomes import collection_failures

    screen = collection_failures(_FakeLedger(_ROWS))
    assert _dag_task(_FakeLedger(_ROWS)) == screen
    assert [(r["artist_name"], r["platform"]) for r in screen] == [
        ("GRiNCH", "soundcloud"), ("Benken", "meta")], "success dropped, newest first"
    assert screen[1]["failing_nights"] == 93 and screen[0]["reason"] == "no cause recorded"


def test_an_unreadable_ledger_is_never_an_empty_list() -> None:
    from src.utils.collection_outcomes import collection_failures

    with pytest.raises(RuntimeError):
        collection_failures(_FakeLedger(RuntimeError("db down")))
    rows = _dag_task(_FakeLedger(RuntimeError("db down")))
    assert len(rows) == 1 and rows[0]["reason"].startswith("check could not run")


def test_a_tenant_is_stalled_from_its_seventh_day() -> None:
    from src.utils.artist_readiness import is_stalled

    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    assert is_stalled(datetime(2026, 9, 29), now)                       # naive = UTC
    assert not is_stalled(datetime(2026, 9, 30, 1, tzinfo=timezone.utc), now)
    assert not is_stalled(None, now)


# ── The readiness half, on a live database ─────────────────────────────────────

@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def two_tenants(db):
    """One silent YouTube with a remembered failed probe; one 10-day-old empty account."""
    ids = []
    for days in (0, 10):
        slug = f"r418-{uuid.uuid4().hex[:10]}"
        ids.append(db.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active, created_at) "
            "VALUES (%s, %s, 'free', TRUE, now() - make_interval(days => %s)) RETURNING id",
            (f"R418 {slug}", slug, days))[0][0])
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, 'youtube', %s::jsonb)", (ids[0], json.dumps({"channel_id": "UCr418"})))
    db.execute_query(
        "INSERT INTO tenant_platform_probe (artist_id, platform, ok, reason, probed_at) "
        "VALUES (%s, 'youtube', FALSE, 'chaîne sans vidéo publique', now())", (ids[0],))
    yield ids
    db.execute_query("DELETE FROM tenant_platform_probe WHERE artist_id = ANY(%s)", (ids,))
    db.execute_query("DELETE FROM artist_credentials WHERE artist_id = ANY(%s)", (ids,))
    db.execute_query("DELETE FROM saas_artists WHERE id = ANY(%s)", (ids,))


@requires_live_db()
def test_the_screen_flags_what_the_nightly_check_flags(db, two_tenants) -> None:
    from src.dashboard.views.admin_collection import readiness_snapshot
    from src.utils.artist_readiness import readiness_red_flags, readiness_stalled_flags

    silent, idle = two_tenants
    snap = readiness_snapshot(db, datetime.now(timezone.utc))
    remembered = {"youtube": (False, "chaîne sans vidéo publique")}
    for aid in two_tenants:
        mine = [(m["key"], m["status"]) for m in snap["red"] if m["artist_id"] == aid]
        dag = [(m["key"], m["status"])
               for m in readiness_red_flags(db, aid, probe=lambda p: remembered.get(p))]
        assert mine == dag, aid
    youtube = next(m for m in snap["red"] if m["artist_id"] == silent)
    assert "chaîne sans vidéo publique" in youtube["next_action"], \
        "the screen must replay the verdict the night measured, not the static hint"
    stalled = {s["artist_id"]: s["platforms"] for s in snap["stalled"]}
    assert stalled.get(idle) == [m["label"] for m in readiness_stalled_flags(db, idle)]
    assert silent not in stalled, "a tenant younger than 7 days is not stalled"
