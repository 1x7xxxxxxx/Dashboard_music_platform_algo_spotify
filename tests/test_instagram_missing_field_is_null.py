"""R510 — an Instagram count the API omits is written NULL, never an invented 0.

Type: Test
Uses: InstagramCollector (db injected, HTTP stubbed)
Depends on: src/collectors/instagram_api_collector.py, src/dashboard/views/instagram.py
Persists in: nothing

A 0 reads as a drop from 1 500 followers to none, on the chart and in « gagnés ».
Both paths are covered: the direct read and the business_discovery fallback.

Mutation record (2026-10-11): seen red with `data.get('followers_count', 0)` on the
direct path, `d.get('followers_count', 0)` on the discovery path, and the
`IS NOT NULL` filter removed from the view.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.collectors.instagram_api_collector import InstagramCollector


def _collector() -> InstagramCollector:
    return InstagramCollector(artist_id=1, access_token="t", ig_user_id="17841",
                              ig_username="someone", db=object())


def _response(status: int, body: dict) -> SimpleNamespace:
    return SimpleNamespace(status_code=status, json=lambda: body, raise_for_status=lambda: None)


def test_direct_read_without_counts_is_none() -> None:
    c = _collector()
    c.session = SimpleNamespace(get=lambda *a, **k: _response(200, {"id": "17841", "username": "x"}))
    stats = c.fetch_stats()
    assert stats["followers_count"] is None
    assert stats["follows_count"] is None and stats["media_count"] is None


def test_discovery_read_without_counts_is_none(monkeypatch) -> None:
    c = _collector()
    code = next(iter(c._DISCOVERY_CODES))
    c.session = SimpleNamespace(get=lambda *a, **k: _response(400, {"error": {"code": code, "message": "x"}}))
    monkeypatch.setattr(c, "_discover", lambda fields: {"id": "17841", "username": "x"})
    stats = c.fetch_stats()
    assert stats["followers_count"] is None and stats["media_count"] is None


def test_the_history_skips_null_followers() -> None:
    import ast
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "src/dashboard/views/instagram.py"
    sql = [n.value for n in ast.walk(ast.parse(src.read_text(encoding="utf-8")))
           if isinstance(n, ast.Constant) and isinstance(n.value, str) and "instagram" in n.value.lower()
           and "followers_count" in n.value and "FROM" in n.value.upper()]
    assert sql, "anti-vacuity: no history query found"
    assert any("followers_count IS NOT NULL" in s for s in sql), \
        "a NULL count reaches int(iloc[-1] - iloc[0]) and crashes « gagnés »"
