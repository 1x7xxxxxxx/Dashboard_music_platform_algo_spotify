"""`make migrate` must never report success while psql errors scrolled past.

Installed 2026-08-21, from the real production migration run that closed R25/R26.

The recipe applies every `migrations/*.sql` in order. That set is idempotent **as a
complete run** — but not file by file, and the difference has teeth:

    024_s4a_song_playlist_adds_redesign.sql   DROP CONSTRAINT s4a_song_playlist_adds_pkey
                                              ADD  PRIMARY KEY (artist_id, song, recorded_at)
    044_playlist_adds_windows.sql             ADD  PRIMARY KEY (artist_id, song, time_window,
                                                                recorded_at)

Since 044 made the key window-aware, 024's three-column key can no longer be
created — it fails on duplicates every single run. 044 then restores the right
one. Run 001..N and production is correct. Stop between 024 and 044 and the table
sits there with no primary key.

`psql` without `ON_ERROR_STOP` exits 0 even when statements failed, and the recipe
used to discard its output entirely — so the target printed success either way.
Continuing past the error is correct; being silent about it is not.

This guard pins the two properties that make silence impossible: the recipe
captures psql's output, and it inspects that output for ERROR/FATAL.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    for d in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test")


REPO = _repo_root()
MAKEFILE = REPO / "Makefile"
SCRIPT = REPO / "tools" / "migrate.sh"


def _migrate_logic() -> str:
    """Wherever the logic lives, this returns it.

    It moved out of the Makefile into `tools/migrate.sh` on 2026-08-21 (R37),
    because `make` is not installed on the production server — a recipe that
    only runs through `make` cannot run where migrations actually matter. The
    guard follows the logic rather than pinning its address.
    """
    if SCRIPT.is_file():
        return SCRIPT.read_text(encoding="utf-8")
    text = MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^migrate:.*?$(.*?)(?=^[A-Za-z0-9_.-]+:)", text, re.S | re.M)
    assert m, "no tools/migrate.sh and no `migrate:` target in the Makefile"
    return m.group(1)


def test_the_migrate_entry_point_exists():
    assert MAKEFILE.is_file(), f"no Makefile at {MAKEFILE}"
    assert "migrate:" in MAKEFILE.read_text(encoding="utf-8"), "no `migrate:` target"
    assert _migrate_logic().strip(), "the migrate logic is empty"


def test_migrations_are_runnable_without_make():
    """R37: `make` is absent from the production server — measured, not assumed.

    `make migrate` exited 127 there on 2026-08-21 while `make deploy` worked,
    because deploy puts its logic in a script and shells into it. Any written
    procedure saying "run make X on prod" is false until migrate does the same.
    """
    assert SCRIPT.is_file(), (
        "tools/migrate.sh is gone — migrations are once again reachable only "
        "through `make`, which the production server does not have."
    )
    body = MAKEFILE.read_text(encoding="utf-8")
    assert "tools/migrate.sh" in body, (
        "the Makefile no longer delegates to tools/migrate.sh — two copies of "
        "the migrate logic will drift, and the one on prod is the one that runs."
    )
    assert "migrate-prod:" in body, (
        "no `migrate-prod` target: the ssh wrapper is what makes the documented "
        "sequence executable from a dev machine (mirrors `deploy`)."
    )


def test_migrate_captures_psql_output():
    """A recipe that pipes psql straight to the terminal cannot inspect it."""
    recipe = _migrate_logic()
    assert "psql" in recipe, "the migrate logic no longer calls psql"
    captured = "$$(docker exec" in recipe or "2>&1" in recipe
    assert captured, (
        "the migrate logic does not capture psql's output. Without capture it "
        "cannot tell a clean run from one where 024 failed — and psql exits 0 "
        "either way, so `make migrate` would print success on both."
    )


def test_migrate_inspects_that_output_for_errors():
    recipe = _migrate_logic()
    assert re.search(r"grep\s+-\w*q?\w*E?\s*['\"].*ERROR", recipe), (
        "the migrate logic captures psql output but never looks for ERROR/FATAL "
        "in it. Capturing and ignoring is the same outcome as not capturing."
    )


def test_migrate_names_the_files_that_errored():
    """Reporting 'something failed' without naming it sends the reader to the logs."""
    recipe = _migrate_logic()
    assert "failed" in recipe, (
        "the migrate logic has no accumulator for the files that errored — it "
        "cannot name them at the end."
    )
    assert "schema-check" in recipe, (
        "the migrate logic reports errors without naming the command that proves "
        "the schema actually landed (`make schema-check`). Cross-cutting rule #10: "
        "a failure message states the fix."
    )


def test_the_024_044_pair_that_makes_this_load_bearing_still_exists():
    """If this pair ever disappears, re-read the guard before trusting it.

    Not a style check: the whole reason `migrate` must keep going after an error
    is that a later migration supersedes an earlier one. Should that stop being
    true, `ON_ERROR_STOP=1` becomes the better design and this test should be the
    thing that says so.
    """
    mig = REPO / "migrations"
    f024 = next(mig.glob("024_*.sql"), None)
    f044 = next(mig.glob("044_*.sql"), None)
    if not (f024 and f044):
        pytest.skip("the 024/044 pair is gone — revisit whether migrate should stop on error")

    drops = "DROP CONSTRAINT s4a_song_playlist_adds_pkey" in f024.read_text(encoding="utf-8")
    restores = "s4a_song_playlist_adds_pkey" in f044.read_text(encoding="utf-8")
    assert drops and restores, (
        "024 no longer drops the key, or 044 no longer restores it. The 'keep going "
        "past an error' design exists for exactly this pair — reconsider it."
    )
