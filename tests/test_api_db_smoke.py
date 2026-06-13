"""DB-gated smoke test for FastAPI data routers — catches schema drift.

Type: Test
Uses: FastAPI TestClient, live Postgres (spotify_etl), forged JWT
Depends on: a provisioned Postgres (CI service or local Docker)

Unlike test_api.py (which mocks the DB and therefore CANNOT see column renames),
this runs every data endpoint against the REAL schema. A query referencing a
renamed/dropped column — the /kpis and /youtube/videos class of bug — fails HERE
(HTTP 500) instead of silently in production. Gated exactly like
test_views_render_smoke: skips cleanly unless the app schema is actually loaded,
so it runs in CI (provisioned Postgres) and locally (real DB), and is a no-op on
an unprovisioned DB.
"""
import os
import socket

import pytest

pytest.importorskip("jose", reason="dev extras not installed — run `make sync`")
pytest.importorskip("fastapi", reason="dev extras not installed — run `make sync`")

# ── DB readiness gate (mirrors test_views_render_smoke) ──────────────────────
_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db_ready() -> bool:
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
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


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} "
           "(socket down or schema not migrated) — API DB-smoke needs the live schema",
)

from fastapi.testclient import TestClient  # noqa: E402

from src.api.auth import create_access_token  # noqa: E402
from src.api.main import app  # noqa: E402

# require_artist_scope/get_current_user trust the signed claims (no DB user lookup),
# so a forged token exercises the routers without seeding a user row.
# - admin (artist_id None) → routers run their broadest UNSCOPED query path.
# - tenant (artist_id=1)   → routers run the scoped `WHERE artist_id=%s` path.
# Both paths must execute against the real schema, so either catches a drifted column.
_ROLES = {
    "admin": {"sub": "smoke-admin", "role": "admin", "artist_id": None},
    "tenant": {"sub": "smoke-tenant", "role": "artist", "artist_id": 1},
}

# Every data-router endpoint that issues SQL (auth/webhook excluded — no DB read).
_DATA_ENDPOINTS = [
    "/kpis",
    "/streams/timeline?limit=5",
    "/streams/summary",
    "/ml/predictions?limit=5",
    "/youtube/videos?limit=5",
    "/artists/me",
    "/artists",
]


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.parametrize("role", list(_ROLES), ids=list(_ROLES))
@pytest.mark.parametrize("path", _DATA_ENDPOINTS)
def test_data_endpoint_no_server_error(client, path, role):
    token = create_access_token(dict(_ROLES[role]))
    r = client.get(path, headers={"Authorization": f"Bearer {token}"})
    # 200 (data or empty) and deliberate 4xx (e.g. /artists → 403 for a tenant) are
    # fine. A 500 means the SQL broke against the real schema = drift / a real bug.
    assert r.status_code != 500, (
        f"{path} as {role} → 500 (schema drift / query bug): {r.text[:300]}"
    )
