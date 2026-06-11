"""Tests for C3 hardening — API rate limit, security headers, session idle timeout.

Uses FastAPI TestClient — no real DB required (the rate limiter rejects
before any route/DB code runs).
"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("jose", reason="dev extras not installed — run `make sync`")
pytest.importorskip("fastapi", reason="dev extras not installed — run `make sync`")

from fastapi.testclient import TestClient  # noqa: E402

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.api.main import app  # noqa: E402
from src.api import security  # noqa: E402
from src.api.deps import get_db  # noqa: E402


@pytest.fixture()
def client():
    """TestClient with a mock DB — no route under test needs real data."""
    from unittest.mock import MagicMock
    import pandas as pd
    db = MagicMock()
    db.fetch_df.return_value = pd.DataFrame()
    db.fetch_query.return_value = []
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _fresh_limiters(monkeypatch):
    """Each test gets empty limiter state (module-level singletons otherwise leak)."""
    monkeypatch.setattr(
        security, "_GLOBAL_LIMITER",
        security.SlidingWindowLimiter(security.RATE_LIMIT_MAX, security.RATE_LIMIT_WINDOW_SECS),
    )
    monkeypatch.setattr(
        security, "_AUTH_LIMITER",
        security.SlidingWindowLimiter(security.AUTH_RATE_LIMIT_MAX, security.AUTH_RATE_LIMIT_WINDOW_SECS),
    )


# ---------------------------------------------------------------------------
# SlidingWindowLimiter (pure)
# ---------------------------------------------------------------------------

class TestSlidingWindowLimiter:
    def test_allows_up_to_max(self):
        lim = security.SlidingWindowLimiter(3, 60)
        assert [lim.hit("k", now=t) for t in (0, 1, 2)] == [None, None, None]

    def test_blocks_over_max_with_retry_after(self):
        lim = security.SlidingWindowLimiter(3, 60)
        for t in (0, 1, 2):
            lim.hit("k", now=t)
        retry = lim.hit("k", now=3)
        assert retry is not None and retry > 0

    def test_window_slides(self):
        lim = security.SlidingWindowLimiter(2, 60)
        lim.hit("k", now=0)
        lim.hit("k", now=1)
        assert lim.hit("k", now=30) is not None   # still inside window
        assert lim.hit("k", now=62) is None       # first hits expired

    def test_keys_are_independent(self):
        lim = security.SlidingWindowLimiter(1, 60)
        assert lim.hit("a", now=0) is None
        assert lim.hit("b", now=0) is None
        assert lim.hit("a", now=1) is not None


# ---------------------------------------------------------------------------
# Middlewares (end-to-end via TestClient)
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    def test_headers_present_on_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Strict-Transport-Security" in r.headers
        assert r.headers["Content-Security-Policy"].startswith("default-src 'none'")
        assert r.headers["Cache-Control"] == "no-store"

    def test_docs_disabled_by_default(self, client):
        # Secure default for public deploy: OpenAPI docs are off unless API_ENABLE_DOCS=1.
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404

    def test_docs_exempt_from_csp(self, monkeypatch):
        # When docs ARE enabled (API_ENABLE_DOCS=1), Swagger UI must be exempt from the
        # strict CSP so it can load. Rebuild the app with docs on to verify.
        import importlib

        from src.api import main as _main
        monkeypatch.setenv("API_ENABLE_DOCS", "1")
        try:
            importlib.reload(_main)
            r = TestClient(_main.app).get("/docs")
            assert r.status_code == 200
            assert "Content-Security-Policy" not in r.headers
            assert r.headers["X-Content-Type-Options"] == "nosniff"
        finally:
            monkeypatch.delenv("API_ENABLE_DOCS", raising=False)
            importlib.reload(_main)


class TestRateLimit:
    def test_429_after_global_budget(self, client, monkeypatch):
        monkeypatch.setattr(security, "_GLOBAL_LIMITER", security.SlidingWindowLimiter(3, 60))
        statuses = [client.get("/artists").status_code for _ in range(4)]
        assert 429 in statuses
        assert statuses[:3].count(429) == 0

    def test_429_carries_retry_after_and_security_headers(self, client, monkeypatch):
        monkeypatch.setattr(security, "_GLOBAL_LIMITER", security.SlidingWindowLimiter(1, 60))
        client.get("/artists")
        r = client.get("/artists")
        assert r.status_code == 429
        assert int(r.headers["Retry-After"]) >= 1
        assert r.headers["X-Content-Type-Options"] == "nosniff"

    def test_health_exempt(self, client, monkeypatch):
        monkeypatch.setattr(security, "_GLOBAL_LIMITER", security.SlidingWindowLimiter(1, 60))
        assert all(client.get("/health").status_code == 200 for _ in range(5))

    def test_auth_endpoint_uses_strict_budget(self, client, monkeypatch):
        monkeypatch.setattr(security, "_AUTH_LIMITER", security.SlidingWindowLimiter(2, 300))
        statuses = [
            client.post("/auth/token", data={"username": "x", "password": "y"}).status_code
            for _ in range(3)
        ]
        assert statuses[2] == 429


# ---------------------------------------------------------------------------
# Streamlit session idle timeout (pure helper)
# ---------------------------------------------------------------------------

class TestSessionIdleTimeout:
    def test_no_previous_activity_is_not_expired(self):
        from src.dashboard.auth import _session_idle_expired
        assert _session_idle_expired(None, now=1000.0) is False

    def test_within_timeout_is_not_expired(self):
        from src.dashboard.auth import _session_idle_expired
        assert _session_idle_expired(1000.0, now=1500.0, timeout_secs=3600) is False

    def test_past_timeout_is_expired(self):
        from src.dashboard.auth import _session_idle_expired
        assert _session_idle_expired(1000.0, now=1000.0 + 3601, timeout_secs=3600) is True
