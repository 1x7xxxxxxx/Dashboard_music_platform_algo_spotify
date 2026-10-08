"""A session idle inside an open transaction is ended — the bound exists and is sane (R468).

Type: Test
Uses: pytest, live Postgres (optional — the static predicates run without a database)
Depends on: migrations/147_idle_in_transaction_timeout.sql
Persists in: nothing

An open transaction holds back the xmin horizon: vacuum can no longer remove dead rows
anywhere in the database for as long as it lives. Prod had no bound until 2026-10-08.
The guard refuses a migration that sets no bound, 0 (disabled), or more than 10 minutes,
and — on a live base — a database without the setting or a role-level override that
silently replaces it (`ALTER ROLE … SET` wins over `ALTER DATABASE … SET`).

The live check reads `pg_db_role_setting` rather than `SHOW` on a fresh connection: the
setting is what NEW sessions get, and reading it needs no credential for the app role.

Mutation record (2026-10-08): value '5min' → '1h' → red; → '0' → red; statement
removed → red; live base with `ALTER ROLE postgres IN DATABASE … SET … = '1h'` → red.
"""
from __future__ import annotations

import os
import re
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = "migrations/147_idle_in_transaction_timeout.sql"
CEILING_MS = 10 * 60 * 1000

_UNITS_MS = {"": 1, "ms": 1, "s": 1000, "min": 60_000, "h": 3_600_000, "d": 86_400_000}
_SETTING = re.compile(
    r"idle_in_transaction_session_timeout\s*(?:=|TO)\s*(?:%L'?\s*,\s*)?",
    re.I)


def to_ms(value: str) -> int:
    """Postgres duration text ('5min', '300000', '30s') → milliseconds."""
    m = re.fullmatch(r"\s*'?(\d+)\s*([a-z]*)'?\s*", value, re.I)
    if not m or m.group(2).lower() not in _UNITS_MS:
        raise ValueError(f"not a Postgres duration: {value!r}")
    return int(m.group(1)) * _UNITS_MS[m.group(2).lower()]


def bound_of(sql: str) -> int | None:
    """The timeout the migration SETS, in ms — None when it sets none.

    Comments are stripped first: a guard is not judged on its own prose. The value is
    the first quoted literal after the setting name (inline, or as the format() arg).
    """
    code = re.sub(r"--[^\n]*", "", sql)
    hit = _SETTING.search(code)
    if not hit:
        return None
    lit = re.search(r"'([^']+)'", code[hit.end():])
    return to_ms(lit.group(1)) if lit else None


def _sane(ms: int | None) -> bool:
    return ms is not None and 0 < ms <= CEILING_MS


def test_the_migration_sets_a_sane_bound() -> None:
    ms = bound_of((ROOT / MIGRATION).read_text(encoding="utf-8"))
    assert _sane(ms), (
        f"{MIGRATION} must set idle_in_transaction_session_timeout to a value in "
        f"(0, 10 min] — read {ms!r} ms")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: missing, disabled and too-long bounds are refused; 5min is not."""
    fmt = ("EXECUTE format('ALTER DATABASE %I SET idle_in_transaction_session_timeout "
           "= %L', current_database(), '{}');")
    assert not _sane(bound_of("-- idle_in_transaction_session_timeout = '5min'\nSELECT 1;"))
    assert not _sane(bound_of(fmt.format("0")))
    assert not _sane(bound_of(fmt.format("1h")))
    assert not _sane(bound_of("ALTER DATABASE x SET idle_in_transaction_session_timeout = '0';"))
    assert _sane(bound_of(fmt.format("5min")))
    assert _sane(bound_of("ALTER DATABASE x SET idle_in_transaction_session_timeout TO '300000';"))


def _db_ready() -> bool:
    if os.environ.get("DATABASE_URL"):
        return True
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=1.5):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _db_ready(), reason="no Postgres reachable on 5433")
def test_the_live_database_carries_the_bound_and_no_role_overrides_it() -> None:
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        pytest.skip("connection unavailable")
    try:
        rows = db.fetch_query(
            "SELECT s.setrole <> 0, unnest(s.setconfig) FROM pg_db_role_setting s "
            "WHERE s.setdatabase IN (0, (SELECT oid FROM pg_database "
            "WHERE datname = current_database()))")
    finally:
        db.close()
    found = [(per_role, cfg.split("=", 1)[1]) for per_role, cfg in rows
             if cfg.startswith("idle_in_transaction_session_timeout=")]
    db_level = [v for per_role, v in found if not per_role]
    if not db_level:
        pytest.skip("this base has not replayed migration 147 — `make migrate`")
    for per_role, value in found:
        assert _sane(to_ms(value)), (
            f"idle_in_transaction_session_timeout={value} "
            f"({'role-level override' if per_role else 'database level'}) is outside "
            "(0, 10 min]: an open transaction can again hold vacuum back")
