"""R511 — YouTube Analytics: three reports, one tenant at a time, an expiry alerted once.

Type: Test
Uses: fake HTTP session, fake db, monkeypatch
Depends on: src/collectors/youtube_analytics_collector.py, airflow/dags/youtube_daily.py,
            tools/dev/youtube_analytics_authorize.py
Persists in: nothing

What must hold:
1. the window covers exactly WINDOW_DAYS days and ends LAG_DAYS before today;
2. `invalid_grant` is AnalyticsAuthorizationExpired (permanent), and no error message
   carries the token;
3. a collection is THREE requests, never one per video;
4. every persisted row names its tenant, and no upsert can rewrite `artist_id`;
5. a tenant without a token is SKIPPED with the re-authorization gesture named; an
   expired token is ONE failure and is then forgotten;
6. the store refuses a token that opens another channel than the declared one;
7. the mint never prints the token on a terminal.

Mutation record (2026-10-11): seen red with `days - 1` → `days`, the invalid_grant branch
removed, a per-video report loop, `artist_id` added to update_columns, the skip reason
without the script name, `_forget_expired_token` call removed, the channel comparison
removed, and the isatty refusal removed.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.collectors import youtube_analytics_collector as yac

_ROOT = Path(__file__).resolve().parents[1]
_TOKEN = "1//SECRET-REFRESH"


def _resp(status: int, body: dict) -> SimpleNamespace:
    return SimpleNamespace(status_code=status, json=lambda: body)


class _Session:
    def __init__(self, token_resp=None, reports=()) -> None:
        self.token_resp = token_resp or _resp(200, {"access_token": "ya29.x"})
        self.reports = list(reports)
        self.gets: list[dict] = []

    def post(self, url, **kw):
        return self.token_resp

    def get(self, url, **kw):
        self.gets.append(kw["params"])
        return self.reports.pop(0)


def _payload(headers: list[str], rows: list[list]) -> SimpleNamespace:
    return _resp(200, {"columnHeaders": [{"name": h} for h in headers], "rows": rows})


def _dag():
    spec = importlib.util.spec_from_file_location("yt_dag_r511", _ROOT / "airflow/dags/youtube_daily.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_window_is_exact_and_lagged() -> None:
    start, end = yac.window(date(2026, 10, 11))
    assert end == date(2026, 10, 8)
    assert (end - start).days + 1 == yac.WINDOW_DAYS


def test_invalid_grant_is_permanent_and_no_message_carries_the_token() -> None:
    s = _Session(token_resp=_resp(400, {"error": "invalid_grant"}))
    with pytest.raises(yac.AnalyticsAuthorizationExpired) as exc:
        yac.refresh_access_token("cid", "csec", _TOKEN, session=s)
    assert _TOKEN not in str(exc.value)
    s = _Session(token_resp=_resp(401, {"error": "invalid_client"}))
    with pytest.raises(yac.AnalyticsApiError) as exc:
        yac.refresh_access_token("cid", "csec", _TOKEN, session=s)
    assert _TOKEN not in str(exc.value) and not isinstance(exc.value, yac.AnalyticsAuthorizationExpired)


def test_a_collection_is_three_requests() -> None:
    m = ["views", "estimatedMinutesWatched", "subscribersGained", "subscribersLost"]
    s = _Session(reports=[
        _payload(["video", *m], [["v1", 10, 30, 4, 1], ["v2", 5, 9, 2, 0]]),
        _payload(["day", *m], [["2026-10-01", 15, 39, 6, 1]]),
        _payload(["day", "insightTrafficSourceType", "views", "estimatedMinutesWatched"],
                 [["2026-10-01", "YT_SEARCH", 7, 20]]),
    ])
    data = yac.YouTubeAnalyticsCollector("cid", "csec", _TOKEN, session=s).collect(date(2026, 10, 11))
    assert len(s.gets) == 3, "one request per report — never one per video"
    assert data["videos"][0] == {"video_id": "v1", "views": 10, "minutes_watched": 30,
                                 "subscribers_gained": 4, "subscribers_lost": 1}
    assert data["traffic"][0]["source_type"] == "YT_SEARCH"
    assert all(g["ids"] == "channel==MINE" for g in s.gets)


def test_every_row_names_its_tenant_and_no_upsert_rewrites_it() -> None:
    calls = []
    db = SimpleNamespace(upsert_many=lambda table, data, **kw: calls.append({**kw, "data": data}))
    data = {"window_end": date(2026, 10, 8), "window_days": 28,
            "videos": [{"video_id": "v1", "views": 1}], "daily": [{"day": "2026-10-01"}],
            "traffic": [{"day": "2026-10-01", "source_type": "SHORTS"}]}
    assert _dag().persist_analytics(db, 7, data) == 3
    assert len(calls) == 3
    for c in calls:
        assert all(r["artist_id"] == 7 for r in c["data"])
        assert "artist_id" in c["conflict_columns"] and "artist_id" not in c["update_columns"]
    assert calls[0]["data"][0]["window_days"] == 28


@pytest.fixture
def dag_env(monkeypatch):
    dag = _dag()
    seen = {"skip": [], "fail": [], "forgot": []}
    logger = importlib.import_module("src.utils.dag_run_logger")
    monkeypatch.setattr(logger, "record_tenant_skip", lambda *a: seen["skip"].append(a))
    monkeypatch.setattr(logger, "record_tenant_failure", lambda *a: seen["fail"].append(a))
    monkeypatch.setattr(logger, "record_tenant_success", lambda *a, **k: None)
    loader = importlib.import_module("src.utils.credential_loader")
    monkeypatch.setattr(loader, "get_active_artists", lambda include_artist_id=None: [(5, "x")])
    ph = importlib.import_module("src.database.postgres_handler")
    monkeypatch.setattr(ph.PostgresHandler, "from_env_or_config",
                        staticmethod(lambda: SimpleNamespace(close=lambda: None)))
    monkeypatch.setattr(dag, "_forget_expired_token", lambda aid: seen["forgot"].append(aid))
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "csec")
    return dag, loader, seen


def test_a_tenant_without_a_token_is_skipped_naming_the_gesture(dag_env, monkeypatch) -> None:
    dag, loader, seen = dag_env
    for creds, word in (({}, "not authorized"), ({"expired_at": "2026-10-01"}, "expired")):
        seen["skip"].clear()
        monkeypatch.setattr(loader, "load_platform_credentials", lambda aid, p, c=creds: c)
        dag.collect_youtube_analytics(run_id="r")
        (reason,) = [a[3] for a in seen["skip"]]
        assert word in reason and "youtube_analytics_authorize.py" in reason


def test_an_expired_token_fails_once_then_is_forgotten(dag_env, monkeypatch) -> None:
    dag, loader, seen = dag_env
    monkeypatch.setattr(loader, "load_platform_credentials",
                        lambda aid, p: {"refresh_token": _TOKEN})

    def expired(self, today):
        raise yac.AnalyticsAuthorizationExpired("invalid_grant")
    monkeypatch.setattr(yac.YouTubeAnalyticsCollector, "collect", expired)
    with pytest.raises(RuntimeError, match="every authorized tenant"):
        dag.collect_youtube_analytics(run_id="r")
    assert len(seen["fail"]) == 1 and seen["forgot"] == [5]


def _authorize():
    spec = importlib.util.spec_from_file_location(
        "yt_authorize_r511", _ROOT / "tools/dev/youtube_analytics_authorize.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_store_refuses_another_channel(monkeypatch) -> None:
    auth = _authorize()
    loader = importlib.import_module("src.utils.credential_loader")
    stored = []
    monkeypatch.setattr(loader, "load_platform_credentials", lambda aid, p: {"channel_id": "UC_DECLARED"})
    monkeypatch.setattr(loader, "store_platform_secrets", lambda *a: stored.append(a))
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "csec")
    s = _Session(reports=[_resp(200, {"items": [{"id": "UC_SOMEONE_ELSE"}]})])
    with pytest.raises(SystemExit):
        auth.store(5, _TOKEN, session=s)
    assert stored == []
    s = _Session(reports=[_resp(200, {"items": [{"id": "UC_DECLARED"}]})])
    assert auth.store(5, _TOKEN, session=s) == 0
    (artist, platform, secrets, extra), = stored
    assert (artist, platform, secrets) == (5, "youtube_analytics", {"refresh_token": _TOKEN})
    assert extra["channel_id"] == "UC_DECLARED"


def test_the_mint_never_prints_the_token_on_a_terminal(monkeypatch) -> None:
    auth = _authorize()
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    with pytest.raises(SystemExit, match="tube"):
        auth.mint()
