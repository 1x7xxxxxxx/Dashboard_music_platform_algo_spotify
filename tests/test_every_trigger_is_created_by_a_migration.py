"""Every trigger on the database is created by init_db.sql or a migration (R396).

Measured 2026-10-05: `trg_calculate_hypeddit_metrics` existed on prod and local, and
only `src/database/hypeddit_schema.py` (run under __main__, imported by nothing) created
it. A base rebuilt from migrations/ had no trigger, so `ctr` stayed NULL in the CSV
export. `make schema-check-local` sees it since R368, but CI does not run that target.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_CREATE = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(\w+)", re.I)


_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)


def declared_triggers(texts: list[str]) -> set[str]:
    """Trigger names CREATEd by executable SQL — a commented-out CREATE declares nothing."""
    return {m.lower() for t in texts for m in _CREATE.findall(_COMMENT.sub("", t))}


def _canonical_texts() -> list[str]:
    files = [REPO / "init_db.sql", *sorted((REPO / "migrations").glob("*.sql"))]
    return [f.read_text(encoding="utf-8") for f in files if f.exists()]


def test_the_reader_sees_both_forms() -> None:
    assert declared_triggers(["CREATE TRIGGER a_b BEFORE", "create or replace trigger c\n"]) == {"a_b", "c"}
    assert declared_triggers(["-- DROP TRIGGER x ON t;"]) == set()
    assert declared_triggers(["-- CREATE TRIGGER gone\n/* CREATE TRIGGER also */"]) == set()


def test_the_hypeddit_trigger_is_in_the_chain() -> None:
    assert "trg_calculate_hypeddit_metrics" in declared_triggers(_canonical_texts())


def test_every_live_trigger_is_declared() -> None:
    try:
        from src.utils.pg_connect import connect
        conn = connect()
    except Exception as exc:  # noqa: BLE001 — no local DB → nothing to compare
        pytest.skip(f"no local database: {exc}")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                        "WHERE c.relnamespace = 'public'::regnamespace AND NOT t.tgisinternal")
            live = {r[0].lower() for r in cur.fetchall()}
    finally:
        conn.close()
    missing = live - declared_triggers(_canonical_texts())
    assert not missing, (
        f"triggers on the database that no migration creates: {sorted(missing)}. A base "
        "rebuilt from migrations/ would not have them — write an additive migration.")
