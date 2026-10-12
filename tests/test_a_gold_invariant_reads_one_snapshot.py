"""Both members of a gold invariant are read in ONE snapshot (R540).

Type: Test
Uses: psycopg2, a live Postgres
Depends on: src/utils/gold_invariants.py (`run`, `ONE_SNAPSHOT`)
Persists in: a probe table created and dropped by the test

Why this exists
---------------
On 2026-10-12, `make test-changed` failed on the gold invariant for artist 1114125
(303 against 406). Run alone, the test passed, and the artist no longer existed: under
READ COMMITTED each member of a pair saw its own snapshot, and a parallel worker
inserted fixtures between the two reads. The same `run()` feeds the nightly
`alert_monitor.check_gold_invariants` in production, where a DAG that writes during
the check would mail a false disagreement.

This test inserts a row from a second connection BETWEEN the left and the right read.
Mutation record — 2026-10-12: with `run()` reading outside `ONE_SNAPSHOT` (the line
`db.execute_query(ONE_SNAPSHOT)` removed), this test is red with one finding for the
probe tenant; with the snapshot it is green.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from tests.db_gate import dsn  # noqa: E402

_CONN = dsn()
_PROBE = "r540_snapshot_probe"

pytestmark = pytest.mark.skipif(_CONN is None, reason="No Postgres on 127.0.0.1:5433")


class _Handler:
    """The two calls `run()` makes, on an autocommit connection like PostgresHandler."""

    def __init__(self, conn, between) -> None:
        self._cur = conn.cursor()
        self._between = between
        self._reads = 0

    def execute_query(self, sql: str) -> None:
        self._cur.execute(sql)

    def fetch_query(self, sql: str) -> list:
        self._cur.execute(sql)
        rows = self._cur.fetchall()
        self._reads += 1
        if self._reads == 1:
            self._between()
        return rows


def test_a_write_between_the_two_members_is_not_a_disagreement(monkeypatch) -> None:
    import psycopg2

    from src.utils import gold_invariants as gi

    reader, writer = psycopg2.connect(**_CONN), psycopg2.connect(**_CONN)
    reader.autocommit = writer.autocommit = True
    with writer.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {_PROBE}")
        cur.execute(f"CREATE TABLE {_PROBE} (artist_id int, v numeric)")
        cur.execute(f"INSERT INTO {_PROBE} VALUES (1, 10)")

    def insert_between() -> None:
        with writer.cursor() as cur:
            cur.execute(f"INSERT INTO {_PROBE} VALUES (1, 5)")

    same = f"SELECT artist_id, SUM(v) FROM {_PROBE} GROUP BY 1"
    probe = gi.Invariant("r540_probe", same, same, "left", "right", "R540 probe")
    monkeypatch.setattr(gi, "INVARIANTS", (probe,))
    monkeypatch.setattr(gi, "bounds_findings", lambda db, reg: ([], 0))
    monkeypatch.setattr(gi, "duplicate_findings", lambda db: [])
    monkeypatch.setattr(gi, "unmapped_findings", lambda db: [])
    try:
        findings, _ = gi.run(_Handler(reader, insert_between))
    finally:
        with writer.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {_PROBE}")
        reader.close()
        writer.close()
    assert findings == [], findings
