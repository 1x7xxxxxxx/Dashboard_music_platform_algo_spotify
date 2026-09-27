"""A SQL file never switches its own database with `\\c` — outside three declared sites.

Type: Test
Uses: nothing — reads the SQL files as text lines
Depends on: init_db.sql, migrations/*.sql
Persists in: nothing

R223 (2026-09-27). Building a throwaway CI-like database with
`psql -d spotify_etl_schema_ci < init_db.sql` wrote into the DEV database instead:
`init_db.sql` carries `\\c spotify_etl`, so psql reconnected and replaced a view and
inserted a test row there; `002_schema_fixes.sql` and `create_missing_tables.sql` did the
same (002 runs UPDATE and DROP VIEW). Every versioned caller targets a database NAMED
`spotify_etl` (CI service, `make canon-pg`'s isolated container, `tools/migrate.sh`), so
the trap only springs by hand — which is exactly when nobody is checking.

The three sites stay: `init_db.sql` needs its `\\c` (the Docker entrypoint runs it
against `postgres`), and the two migrations are applied everywhere already. A NEW one
is refused. A migration never needs to name its database: the caller chooses it.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_DECLARED = {
    "init_db.sql": "the Docker entrypoint runs it against `postgres`; it must reconnect",
    "migrations/002_schema_fixes.sql": "already applied everywhere (2026-06)",
    "migrations/create_missing_tables.sql": "already applied everywhere (legacy bootstrap)",
}
_SWITCH = re.compile(r"^\s*\\(c|connect)(\s|$)")


def _switches(text: str) -> list[int]:
    return [i for i, line in enumerate(text.splitlines(), 1) if _SWITCH.match(line)]


def test_no_new_sql_file_switches_its_database() -> None:
    offenders = []
    for p in sorted([ROOT / "init_db.sql", *(ROOT / "migrations").glob("*.sql")]):
        rel = str(p.relative_to(ROOT))
        if rel not in _DECLARED and _switches(p.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert not offenders, (
        f"{offenders} reconnect with `\\c`: applied to any other database by hand, they "
        "write into the one they name. A migration never names its database — drop it.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    assert _switches("-- header\n\\c spotify_etl\nSELECT 1;") == [2]
    assert _switches("\\connect spotify_etl") == [1]
    assert _switches("-- a comment about \\c spotify_etl\nSELECT '\\c';") == []
