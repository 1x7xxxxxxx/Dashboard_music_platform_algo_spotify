"""Unit tests for the FastAPI REST backend (Brick 14).

Uses FastAPI TestClient — no real DB or Airflow required.
The DB dependency is overridden with a mock ``PostgresHandler``-like object.

Skipped gracefully when dev extras (fastapi, python-jose) aren't installed —
local devs can run `make test` without setting up the full API stack, while CI
(which installs --extra dev) still runs these tests.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Skip whole module if the API stack isn't installed locally. Must run BEFORE
# the `src.api.*` imports below — those transitively pull jose + fastapi.
pytest.importorskip("jose", reason="dev extras not installed — run `make sync`")
pytest.importorskip("fastapi", reason="dev extras not installed — run `make sync`")

from fastapi.testclient import TestClient  # noqa: E402

# Ensure project root on path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.api.main import app  # noqa: E402
from src.api.auth import create_access_token, verify_password  # noqa: E402
from src.api.deps import get_db  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _artist_token(artist_id: int = 1) -> str:
    return create_access_token({"sub": "testartist", "role": "artist", "artist_id": artist_id})


def _admin_token() -> str:
    return create_access_token({"sub": "admin", "role": "admin", "artist_id": None})


def _mock_db(data: dict[str, pd.DataFrame] | None = None) -> MagicMock:
    """Return a mock DB that responds to fetch_df calls with pre-set DataFrames."""
    db = MagicMock()
    data = data or {}

    def _fetch_df(query: str, params=None):
        for key, df in data.items():
            if key.lower() in query.lower():
                return df
        return pd.DataFrame()

    db.fetch_df.side_effect = _fetch_df
    db.close = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_no_auth():
    """TestClient with no DB override — tests that don't hit the DB."""
    return TestClient(app)


@pytest.fixture()
def mock_db():
    return _mock_db()


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health(client_no_auth):
    r = client_no_auth.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------

def test_create_and_decode_token():
    from src.api.auth import decode_token
    token = create_access_token({"sub": "alice", "role": "artist", "artist_id": 2})
    payload = decode_token(token)
    assert payload["sub"] == "alice"
    assert payload["role"] == "artist"
    assert payload["artist_id"] == 2


def test_expired_token_raises():
    from datetime import timedelta
    from jose import JWTError
    from src.api.auth import decode_token
    token = create_access_token({"sub": "alice"}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(JWTError):
        decode_token(token)


def test_verify_password():
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = ctx.hash("secret")
    assert verify_password("secret", hashed) is True
    assert verify_password("wrong", hashed) is False


# ---------------------------------------------------------------------------
# Auth: GET without token → 401
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "/artists/me",
    "/artists",
    "/streams/timeline",
    "/streams/summary",
    "/youtube/videos",
    "/ml/predictions",
    "/kpis",
])
def test_protected_endpoints_require_token(url, client_no_auth):
    r = client_no_auth.get(url)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# /auth/token — login
# ---------------------------------------------------------------------------

# Login now authenticates against saas_users (DB), not config.yaml. Build a mock DB
# whose fetch_query returns one saas_users row (column order must match
# authenticate_api_user): (id, username, email, password_hash, artist_id, role,
# email_verified, failed_login_attempts, locked_until, totp_enabled).
def _login_db(row=None):
    db = MagicMock()
    db.fetch_query.return_value = [row] if row is not None else []
    db.execute_query.return_value = None
    db.close = MagicMock()
    return db


def _user_row(pw="correct", *, verified=True, totp=False, locked_until=None,
              artist_id=1, role="artist"):
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return (1, "alice", "alice@x.com", ctx.hash(pw), artist_id, role, verified,
            0, locked_until, totp)


def test_login_db_unavailable():
    """DB unreachable → 503 (replaces the old 'no auth config' case)."""
    app.dependency_overrides[get_db] = lambda: None
    try:
        r = TestClient(app).post("/auth/token", data={"username": "x", "password": "y"})
        assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_login_unknown_user():
    app.dependency_overrides[get_db] = lambda: _login_db(None)
    try:
        r = TestClient(app).post("/auth/token", data={"username": "ghost", "password": "y"})
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_login_wrong_password():
    app.dependency_overrides[get_db] = lambda: _login_db(_user_row("correct"))
    try:
        r = TestClient(app).post("/auth/token", data={"username": "alice", "password": "wrong"})
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_login_unverified_403():
    app.dependency_overrides[get_db] = lambda: _login_db(_user_row("correct", verified=False))
    try:
        r = TestClient(app).post("/auth/token", data={"username": "alice", "password": "correct"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_login_totp_blocked_403():
    """2FA-enabled accounts must not get a password-only token (would bypass 2FA)."""
    app.dependency_overrides[get_db] = lambda: _login_db(_user_row("correct", totp=True))
    try:
        r = TestClient(app).post("/auth/token", data={"username": "alice", "password": "correct"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_login_success():
    app.dependency_overrides[get_db] = lambda: _login_db(_user_row("correct"))
    try:
        r = TestClient(app).post("/auth/token", data={"username": "alice", "password": "correct"})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["role"] == "artist"
        assert body["artist_id"] == 1
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /artists
# ---------------------------------------------------------------------------

def test_get_me_artist():
    db = _mock_db({"saas_artists": pd.DataFrame([{"id": 1, "name": "Test Artist", "active": True}])})
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        token = _artist_token(artist_id=1)
        r = client.get("/artists/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["name"] == "Test Artist"
    finally:
        app.dependency_overrides.clear()


def test_get_me_admin():
    app.dependency_overrides[get_db] = lambda: _mock_db()
    try:
        client = TestClient(app)
        r = client.get("/artists/me", headers={"Authorization": f"Bearer {_admin_token()}"})
        assert r.status_code == 200
        assert r.json()["role"] == "admin"
    finally:
        app.dependency_overrides.clear()


def test_list_artists_requires_admin():
    app.dependency_overrides[get_db] = lambda: _mock_db()
    try:
        client = TestClient(app)
        r = client.get("/artists", headers={"Authorization": f"Bearer {_artist_token()}"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_list_artists_admin():
    df = pd.DataFrame([
        {"id": 1, "name": "A", "active": True},
        {"id": 2, "name": "B", "active": False},
    ])
    app.dependency_overrides[get_db] = lambda: _mock_db({"saas_artists": df})
    try:
        client = TestClient(app)
        r = client.get("/artists", headers={"Authorization": f"Bearer {_admin_token()}"})
        assert r.status_code == 200
        assert len(r.json()) == 2
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /streams
# ---------------------------------------------------------------------------

def test_streams_timeline_empty():
    app.dependency_overrides[get_db] = lambda: _mock_db()
    try:
        client = TestClient(app)
        r = client.get("/streams/timeline", headers={"Authorization": f"Bearer {_artist_token()}"})
        assert r.status_code == 200
        assert r.json() == []
    finally:
        app.dependency_overrides.clear()


def test_streams_timeline_data():
    df = pd.DataFrame([
        {"date": "2025-01-01", "song": "Song A", "streams": 1000},
        {"date": "2025-01-02", "song": "Song B", "streams": 500},
    ])
    app.dependency_overrides[get_db] = lambda: _mock_db({"s4a_song_timeline": df})
    try:
        client = TestClient(app)
        r = client.get("/streams/timeline", headers={"Authorization": f"Bearer {_artist_token()}"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        assert data[0]["song"] == "Song A"
        assert data[0]["streams"] == 1000
    finally:
        app.dependency_overrides.clear()


def test_streams_summary_empty():
    df = pd.DataFrame([{"total_streams": 0, "unique_songs": 0, "latest_date": None}])
    app.dependency_overrides[get_db] = lambda: _mock_db({"s4a_song_timeline": df})
    try:
        client = TestClient(app)
        r = client.get("/streams/summary", headers={"Authorization": f"Bearer {_artist_token()}"})
        assert r.status_code == 200
        assert r.json()["total_streams"] == 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /youtube
# ---------------------------------------------------------------------------

def test_youtube_videos_data():
    df = pd.DataFrame([{
        "video_id": "abc123", "title": "My Video", "views": 5000,
        "likes": 200, "comments": 30, "collected_at": "2025-06-01",
    }])
    app.dependency_overrides[get_db] = lambda: _mock_db({"youtube_video_stats": df})
    try:
        client = TestClient(app)
        r = client.get("/youtube/videos", headers={"Authorization": f"Bearer {_artist_token()}"})
        assert r.status_code == 200
        assert r.json()[0]["video_id"] == "abc123"
        assert r.json()[0]["views"] == 5000
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /ml
# ---------------------------------------------------------------------------

def test_ml_predictions_data():
    # Contract = the real ml_song_predictions schema: the three algo probabilities +
    # prediction_date (no score/tier — that was the KNOWN-BROKEN contract).
    df = pd.DataFrame([{
        "song": "Track X", "prediction_date": "2025-06-01",
        "dw_probability": 0.87, "rr_probability": 0.42, "radio_probability": 0.12,
    }])
    app.dependency_overrides[get_db] = lambda: _mock_db({"ml_song_predictions": df})
    try:
        client = TestClient(app)
        r = client.get("/ml/predictions", headers={"Authorization": f"Bearer {_artist_token()}"})
        assert r.status_code == 200
        assert r.json()[0]["song"] == "Track X"
        assert r.json()[0]["dw_probability"] == 0.87
        assert r.json()[0]["radio_probability"] == 0.12
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /kpis
# ---------------------------------------------------------------------------

def test_kpis_all_none_when_empty():
    app.dependency_overrides[get_db] = lambda: _mock_db()
    try:
        client = TestClient(app)
        r = client.get("/kpis", headers={"Authorization": f"Bearer {_artist_token()}"})
        assert r.status_code == 200
        body = r.json()
        assert body["spotify_streams_7d"] is None
        assert body["ml_top_song"] is None
    finally:
        app.dependency_overrides.clear()
