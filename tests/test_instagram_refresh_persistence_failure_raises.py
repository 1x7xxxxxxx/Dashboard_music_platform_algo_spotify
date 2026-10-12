"""A refreshed Meta token that could not be stored fails the collector run (R524 b).

Type: Test
Uses: src.collectors.instagram_api_collector.InstagramAPICollector._check_proactive_refresh

Rule 6 (collectors must raise). R398 made `update_platform_secret` raise
`SecretNotPersistedError`; the collector's outer `except Exception` turned it back into
`return False` — « refresh failed, keep the old token » — and `_check_proactive_refresh`
logged it at DEBUG. The new token was lost at the end of the run and nobody heard of it.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.collectors import instagram_api_collector as mod
from src.utils.credential_loader import SecretNotPersistedError


class _Session:
    def get(self, *a, **k):
        return SimpleNamespace(status_code=200,
                               json=lambda: {"access_token": "NEW", "expires_in": 5184000})


class _DB:
    def fetch_query(self, *a, **k):
        return [(datetime.utcnow() + timedelta(days=3),)]


def _collector():
    c = mod.InstagramCollector.__new__(mod.InstagramCollector)
    c.artist_id, c.app_id, c.app_secret, c.access_token = 7, "app", "secret", "OLD"
    c.base_url, c.session, c.db = "https://graph.invalid", _Session(), _DB()
    return c


def _refuse(*a, **k):
    raise SecretNotPersistedError("disk full")


@pytest.fixture()
def prod(monkeypatch):
    from src.utils import credential_loader, instance_identity
    monkeypatch.setattr(instance_identity, "is_production", lambda: True)
    return credential_loader


def test_a_refused_persist_fails_the_proactive_refresh(prod, monkeypatch):
    monkeypatch.setattr(prod, "update_platform_secret", _refuse)
    with pytest.raises(SecretNotPersistedError):
        _collector()._check_proactive_refresh()


def test_any_persist_error_is_said_as_not_persisted(prod, monkeypatch):
    def boom(*a, **k):
        raise OSError("connection reset")
    monkeypatch.setattr(prod, "update_platform_secret", boom)
    with pytest.raises(SecretNotPersistedError):
        _collector()._refresh_access_token()


def test_a_meta_refusal_still_keeps_the_old_token(prod, monkeypatch):
    """The other branch is unchanged: Meta saying no is not a lost secret."""
    c = _collector()
    c.session = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(
        status_code=400, json=lambda: {"error": "expired"}))
    assert c._refresh_access_token() is False
    assert c.access_token == "OLD"
