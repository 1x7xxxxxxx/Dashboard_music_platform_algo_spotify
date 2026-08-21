"""A migration replayed ALONE must never damage a schema a later one repaired.

Measured 2026-08-21, while introducing the schema_migrations ledger.

Until then the strategy was "reapply all 70 files every time", and 024 failing was
survivable only because 044 ran afterwards and put the right primary key back. The
ledger changed that: a file that never succeeds is never recorded, so it is retried
ALONE on every run — and 024's first statement was an unguarded
`DROP CONSTRAINT s4a_song_playlist_adds_pkey`.

Each retry therefore DESTROYED 044's key and failed to create its own, leaving
`s4a_song_playlist_adds` with no primary key at all. Observed live: the table was
found keyless, and it was the ledger's own introduction that did it.

Error class: unguarded-drop-replayed-alone (.claude/dev-docs/error-classes.md).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = sorted((ROOT / "migrations").glob("*.sql"))

# A DROP is safe when it says IF EXISTS, or when it sits inside a DO block that
# tested for the object first (the 061 shape).
_DROP = re.compile(r"\bDROP\s+(CONSTRAINT|COLUMN|INDEX|TABLE|VIEW)\b", re.I)
_GUARDED = re.compile(r"\bDROP\s+(CONSTRAINT|COLUMN|INDEX|TABLE|VIEW)\s+IF\s+EXISTS\b", re.I)


def _strip_sql_comments(text: str) -> str:
    """A file that DOCUMENTS the defect in a comment must not trip its own guard."""
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def test_there_are_migrations_to_check() -> None:
    """Without this, an empty glob would make the sweep below pass on nothing."""
    assert len(MIGRATIONS) > 50, f"only {len(MIGRATIONS)} migrations found — bad path?"


@pytest.mark.parametrize("path", MIGRATIONS, ids=lambda p: p.name)
def test_no_unguarded_drop(path: Path) -> None:
    code = _strip_sql_comments(path.read_text(encoding="utf-8"))
    inside_do = False
    for lineno, line in enumerate(code.splitlines(), 1):
        stripped = line.strip()
        if re.search(r"\bDO\s*\$\$", stripped, re.I):
            inside_do = True
        elif stripped.startswith("END $$") or stripped.startswith("END$$"):
            inside_do = False
        if not _DROP.search(line) or _GUARDED.search(line):
            continue
        assert inside_do, (
            f"{path.name}:{lineno} drops an object with no IF EXISTS and outside a "
            f"guarded DO block:\n    {stripped}\n"
            "Replayed on its own — which the ledger now does for any file that never "
            "succeeds — this destroys whatever currently holds that name."
        )


def test_024_is_neutralised_once_044_has_run() -> None:
    """The specific pair. 024's key became impossible the day 044 made it windowed."""
    text = (ROOT / "migrations/024_s4a_song_playlist_adds_redesign.sql").read_text(
        encoding="utf-8")
    assert "time_window" in text and "RETURN;" in text, (
        "024 no longer checks for 044's marker column before touching the primary "
        "key. Replaying it alone drops the live key and cannot recreate its own."
    )
    code = _strip_sql_comments(text)
    assert "DROP CONSTRAINT s4a_song_playlist_adds_pkey;" not in code, (
        "024 drops the primary key unguarded again — the exact statement that left "
        "the table keyless on 2026-08-21."
    )
