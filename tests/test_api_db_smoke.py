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

# LE GARDE ÉTAIT AVEUGLE DEPUIS QUE `get_current_user` RELIT LA BASE.
#
# Ce commentaire disait, à raison le jour où il a été écrit, que les claims signés
# suffisaient. R24 a ajouté une relecture de `saas_users` dans `get_current_user`
# (`src/api/deps.py:71`) : un jeton forgé pour un `sub` qui n'existe pas en base est
# désormais refusé en **401, AVANT d'atteindre le moindre routeur**.
#
# Les 28 assertions de ce fichier sont `status != 500`. Elles étaient donc toutes
# satisfaites par des 401, et le fichier n'exécutait plus une seule requête SQL —
# mesuré le 2026-09-10, et c'est **pourquoi** un `/kpis` cassé en production est passé
# sur une suite verte. `dependency_overrides` court-circuite la relecture : ce test
# garde la dérive de SCHÉMA, pas l'authentification, qui a ses propres tests.
# - admin (artist_id None) → routers run their broadest UNSCOPED query path.
# - tenant (artist_id=N)   → routers run the scoped `WHERE artist_id=%s` path.
# MULTI-TENANT: parametrise over EVERY active artist (not just artist 1) — the Benken class
# of bug appeared only for tenant #2 (a query OK for artist 1 but 500ing for artist 12 on
# NULL/empty handling). A sparse tenant (no data) is the most likely to expose it.
def _active_artist_ids(limit: int = 3) -> list:
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        try:
            rows = db.fetch_query(
                "SELECT id FROM saas_artists WHERE active = TRUE ORDER BY id LIMIT %s",
                (limit,),
            )
        finally:
            db.close()
        return [r[0] for r in rows] or [1]
    except Exception:
        return [1]


_ROLES = {"admin": {"sub": "smoke-admin", "role": "admin", "artist_id": None}}
for _aid in _active_artist_ids():
    _ROLES[f"tenant{_aid}"] = {"sub": f"smoke-tenant-{_aid}", "role": "artist", "artist_id": _aid}

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


@pytest.fixture(autouse=True)
def _bypass_user_lookup(request):
    """Le routeur reçoit l'identité directement, sans relecture de `saas_users`."""
    from src.api.deps import get_current_user
    role = request.node.callspec.params.get("role") if hasattr(request.node, "callspec") else None
    if role is None:
        yield
        return
    app.dependency_overrides[get_current_user] = lambda: dict(_ROLES[role])
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


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
    assert r.status_code != 401, (
        f"{path} as {role} → 401 : le routeur n'a PAS été atteint, donc aucune requête "
        "SQL n'a été exécutée et ce test ne prouve rien. C'est l'état dans lequel il "
        "est resté trois semaines."
    )


def test_at_least_one_endpoint_actually_returns_data(client):
    """Non-vacuité : une suite qui ne voit que des refus ne garde rien.

    Écrite après avoir mesuré que les 28 assertions `!= 500` de ce fichier étaient
    toutes satisfaites par des 401. Un test qui passe sans jamais toucher ce qu'il
    prétend garder est pire qu'absent : il occupe la place du garde.
    """
    from src.api.deps import get_current_user
    app.dependency_overrides[get_current_user] = lambda: dict(_ROLES["admin"])
    try:
        codes = {p: client.get(p, headers={"Authorization": "Bearer x"}).status_code
                 for p in _DATA_ENDPOINTS}
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert 200 in codes.values(), (
        "aucun des endpoints de données ne rend 200 : " + repr(codes)
        + ". Le SQL n'est donc jamais exécuté contre le schéma réel.")
