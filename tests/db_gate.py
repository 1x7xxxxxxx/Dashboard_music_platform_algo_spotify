"""One place that answers "is there a provisioned Postgres?".

The same 25-line probe was copy-pasted into five test modules, each with its own
comment explaining the same two subtleties. A test that needs the live schema now
writes one line:

    pytestmark = requires_live_db()

Both subtleties stay in force, in one place:

  * a TCP check alone is not enough — CI can start an EMPTY `postgres:17` on 5433,
    so the socket connects while every query fails on a missing relation. The
    authoritative probe reads a core table.
  * when `DATABASE_URL` is set (CI, or a throwaway container on another port) the
    hardcoded 5433 pre-check must be skipped, or the module skips on a DB that is
    actually there.
"""
from __future__ import annotations

import os
import socket

import pytest

DB_HOST, DB_PORT = "127.0.0.1", 5433

_SKIP_REASON = (
    f"No provisioned Postgres on {DB_HOST}:{DB_PORT} (socket down or schema not "
    "migrated), and no DATABASE_URL — this suite needs the live schema"
)


def db_ready() -> bool:
    """True when a Postgres carrying THIS app's schema is reachable."""
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((DB_HOST, DB_PORT), timeout=1.5):
                pass
        except OSError:
            return False
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return False
        try:
            db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


def requires_live_db():
    """Module-level marker: `pytestmark = requires_live_db()`."""
    return pytest.mark.skipif(not db_ready(), reason=_SKIP_REASON)
