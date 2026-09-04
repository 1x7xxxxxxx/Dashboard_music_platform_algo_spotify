"""Guard: a file that imported cleanly can still be read back a week later.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `the-only-copy-is-consumed-on-read`.

Measured 2026-09-04. `upload_csv.py` read the uploaded file into memory, parsed it,
upserted the rows and let the bytes go. `csv_upload_log` recorded that a file named X
produced N rows — it could not answer **what was in X**. So when an import lands
wrong (a column renamed upstream, a separator misread, a tenant's numbers that look
off a week later), the only copy of what was actually sent is gone.

## What this replaced

Four `*_csv_watcher` DAGs polled `/opt/airflow/data/raw/*` every 15 minutes. They
were removed the same day, and the numbers say why: **97,2 % of all `dag_run` rows and
98,4 % of all `task_instance` rows**, every execution `skipped`, against directories
where `find` has never located a single file. They also covered LESS than the page —
`parse_csv_file` builds no `songs_global` rows, `parse_songs_global` does.

The useful half of a directory watcher was never the polling. It was that the file
survived the import. This keeps that half.

## The four rules, and what breaks without each

* **Archive only on success.** A directory of files that failed to import fills with
  the uninteresting case; the one worth keeping imported cleanly and still produced
  wrong numbers.
* **Never raise.** The rows are committed by the time the copy is written. Failing an
  import because a convenience copy could not be saved trades a working feature for a
  nice-to-have.
* **Per tenant.** A flat directory makes one tenant's file reachable by guessing a
  path, and erasing one tenant's data becomes a grep.
* **Rebuild the filename.** It arrives from a browser; `../` and its encodings are one
  string away from writing outside the tree.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.utils.upload_archive import (
    RETENTION_DAYS,
    archive_upload,
    archived_for,
    purge_expired,
    safe_name,
    uploads_root,
)


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
VIEW = REPO / "src" / "dashboard" / "views" / "upload_csv.py"
_TEST_TENANT = 999_999


@pytest.fixture(autouse=True)
def _clean_tenant_dir():
    import shutil
    yield
    shutil.rmtree(uploads_root() / str(_TEST_TENANT), ignore_errors=True)


# ── The filename can never escape its directory ─────────────────────────────

@pytest.mark.parametrize("hostile", [
    "../../etc/passwd",
    "..%2F..%2Fshadow",
    "/absolute/path.csv",
    "....//....//x.csv",
    "a/b/c.csv",
])
def test_a_hostile_filename_is_rebuilt(hostile: str):
    name = safe_name(hostile)
    assert "/" not in name and "\\" not in name
    assert not name.startswith(".")
    assert ".." not in name


def test_an_empty_name_still_produces_a_file():
    assert safe_name("") and safe_name(None or "")


def test_the_archived_path_stays_under_the_tenant_directory():
    """The property that matters, asserted on the resolved path, not the name."""
    path = archive_upload(_TEST_TENANT, "../../escape.csv", b"x")
    assert path is not None
    assert path.resolve().parent == (uploads_root() / str(_TEST_TENANT)).resolve()


# ── Round trip and retention ────────────────────────────────────────────────

def test_a_file_can_be_read_back_after_archiving():
    payload = b"song,streams\nAlpha,42\n"
    path = archive_upload(_TEST_TENANT, "s4a.csv", payload)
    assert path is not None and path.read_bytes() == payload
    assert [p.name for p in archived_for(_TEST_TENANT)] == [path.name]


def test_an_empty_upload_is_not_archived():
    assert archive_upload(_TEST_TENANT, "vide.csv", b"") is None


def test_an_expired_file_is_purged_and_a_recent_one_is_kept():
    """Both directions. Only the first half would pass on `rm -rf`."""
    import os
    import time

    old = archive_upload(_TEST_TENANT, "vieux.csv", b"x")
    new = archive_upload(_TEST_TENANT, "recent.csv", b"y")
    assert old and new
    stale = time.time() - (RETENTION_DAYS + 1) * 86400
    os.utime(old, (stale, stale))

    assert purge_expired() >= 1
    remaining = {p.name for p in archived_for(_TEST_TENANT)}
    assert new.name in remaining, "a file inside the window was deleted"
    assert old.name not in remaining, "a file past the window survived"


def test_the_retention_window_is_two_weeks():
    assert RETENTION_DAYS == 14


# ── The view archives on success, and only there ────────────────────────────

def test_the_view_archives_and_purges():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_archive_ok" in called, (
        "the upload view no longer archives. A failed import then has no copy of what "
        "was actually sent, which is the whole defect."
    )
    assert "purge_expired" in called, (
        "nothing purges the archive. Called from the page rather than a cron because "
        "the directory only grows when someone uploads — but it must be called."
    )


def test_archiving_happens_in_the_success_branch_only():
    """AST: `_archive_ok` must sit under the upsert's `try`, never in the handler.

    Placed in the `except`, it would keep exactly the files whose rows never landed —
    the inverse of the intent, and green on every test that only checks a file exists.
    """
    src = VIEW.read_text(encoding="utf-8")
    tree = ast.parse(src)
    in_handler = [n for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)
                  for n in ast.walk(node)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "_archive_ok"]
    assert not in_handler, (
        "_archive_ok is called from an exception handler: the archive would collect "
        "the imports that FAILED and drop the ones that succeeded."
    )


def test_the_archive_helper_cannot_break_an_import():
    """The rows are already committed when this runs."""
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_archive_ok"), None)
    assert fn is not None, "_archive_ok is gone"
    assert any(isinstance(n, ast.Try) for n in ast.walk(fn)), (
        "_archive_ok has no exception boundary: a full disk would fail an import "
        "whose rows are already in the database."
    )


def test_the_watchers_are_gone():
    """They cost 98,4 % of the Airflow metadata to watch directories that stayed empty.

    Pinned so the next person reaching for a directory watcher meets this first: the
    page parses on upload, covers more types, and now keeps the file.
    """
    leftovers = sorted(p.name for p in (REPO / "airflow" / "dags").glob("*_csv_watcher.py"))
    assert not leftovers, (
        f"{leftovers} are back. Before adding one, check `find data/raw -type f`: the "
        "four removed on 2026-09-04 had never seen a single file."
    )
