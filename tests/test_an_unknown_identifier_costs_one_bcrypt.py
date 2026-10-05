"""An unknown identifier pays the same bcrypt as a real account (R401).

Type: Guard
Uses: src.dashboard.auth._authenticate_user, src.api.auth.authenticate_api_user
Depends on: nothing (the database is a stub that knows no one)
Persists in: nothing

Found by the security review of R398 (2026-10-05): an unknown identifier returned at
once, an existing account paid bcrypt plus the lockout UPDATE — the response time of the
public form and of `POST /auth/token` said which identifiers exist.
"""
from __future__ import annotations

import pytest


class _NoOne:
    """A database in which no identifier exists — or one with no password (Google)."""

    def __init__(self, rows: list) -> None:
        self.rows = rows

    def fetch_query(self, *_a, **_k) -> list:
        return self.rows


_GOOGLE_API = [(7, "g", "g@x", None, 1, "artist", True, 0, None, False, 0)]


@pytest.mark.parametrize(("module", "call", "rows"), [
    ("src.dashboard.auth", "_authenticate_user", []),
    ("src.api.auth", "authenticate_api_user", []),
    ("src.api.auth", "authenticate_api_user", _GOOGLE_API),
])
def test_a_login_with_nothing_to_check_still_runs_bcrypt_once(module, call, rows,
                                                              monkeypatch) -> None:
    import importlib

    mod = importlib.import_module(module)
    calls: list[str] = []
    real = mod.verify_password
    monkeypatch.setattr(mod, "verify_password", lambda p, h: calls.append(h) or real(p, h))
    fn = getattr(mod, call)
    args = ("ghost", "pw", _NoOne(rows)) if call == "_authenticate_user" \
        else (_NoOne(rows), "ghost", "pw")
    user, _err = fn(*args)
    assert user is None
    assert len(calls) == 1, (
        f"{module}.{call} ran bcrypt {len(calls)} times for an identifier with nothing to "
        "check — the response time tells an attacker which identifiers exist")
