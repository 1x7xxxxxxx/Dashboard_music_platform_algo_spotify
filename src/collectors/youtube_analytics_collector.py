"""YouTube Analytics API — three figures the public Data API does not give (R511).

Type: Feature
Uses: requests, Google OAuth token endpoint, youtubeAnalytics.reports.query
Triggers: airflow/dags/youtube_daily.py::collect_youtube_analytics
Depends on: a per-tenant refresh_token (artist_credentials, platform 'youtube_analytics'),
            minted by tools/dev/youtube_analytics_authorize.py; the central Google OAuth app
            (GOOGLE_OAUTH_CLIENT_ID / _SECRET, ADR-006)
Persists in: nothing — the DAG writes youtube_analytics_{video_window,channel_daily,traffic_daily}

Three reports, one request each (never one per video):
  * per video over a window — subscribers gained/lost, views, minutes watched;
  * per day — the same, EXACT (the Data API rounds subscribers to 3 significant digits);
  * per day and traffic source.
Analytics consolidates with a ~2-3 day lag, so the window ends LAG_DAYS before today.

Errors raise (rule #6). An `invalid_grant` on refresh — the artist revoked access, or the
token lapsed — is `AnalyticsAuthorizationExpired`: permanent, retrying cannot fix it.
"""
from __future__ import annotations

import contextlib

from datetime import date, timedelta

import requests

from src.utils.failure_kinds import PermanentFailure

TOKEN_URL = "https://oauth2.googleapis.com/token"
REPORTS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
SCOPES = ("https://www.googleapis.com/auth/yt-analytics.readonly",
          "https://www.googleapis.com/auth/youtube.readonly")
LAG_DAYS = 3
WINDOW_DAYS = 28
_TIMEOUT = 30
_METRICS = "views,estimatedMinutesWatched,subscribersGained,subscribersLost"
# API metric name → column name
_COLUMNS = {"views": "views", "estimatedMinutesWatched": "minutes_watched",
            "subscribersGained": "subscribers_gained", "subscribersLost": "subscribers_lost"}


class AnalyticsAuthorizationExpired(PermanentFailure, RuntimeError):
    """Google refused the refresh_token (`invalid_grant`): the artist must authorize again."""


class AnalyticsApiError(RuntimeError):
    """A report request failed — the HTTP status and Google's reason, never the token."""


def window(today: date, lag: int = LAG_DAYS, days: int = WINDOW_DAYS) -> tuple[date, date]:
    """[start, end] covering exactly `days` days, ending `lag` days before `today`."""
    end = today - timedelta(days=lag)
    return end - timedelta(days=days - 1), end


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str,
                         session=requests) -> str:
    resp = session.post(TOKEN_URL, timeout=_TIMEOUT, data={
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token"})
    if resp.status_code == 400 and _reason(resp) == "invalid_grant":
        raise AnalyticsAuthorizationExpired("Google refused the refresh_token (invalid_grant)")
    if resp.status_code != 200:
        raise AnalyticsApiError(f"token refresh HTTP {resp.status_code}: {_reason(resp)}")
    return resp.json()["access_token"]


def _reason(resp) -> str:
    """Describe a refused response — every caller raises with it, nothing is swallowed."""
    body = {"error": "unreadable body"}
    with contextlib.suppress(ValueError):
        body = resp.json()
    err = body.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err.get("status") or "unknown")[:200]
    return str(err or "unknown")[:200]


def rows_as_dicts(payload: dict) -> list[dict]:
    """A reports.query answer as one dict per row, metric columns renamed."""
    names = [_COLUMNS.get(h["name"], h["name"]) for h in payload.get("columnHeaders", [])]
    return [dict(zip(names, row)) for row in payload.get("rows") or []]


class YouTubeAnalyticsCollector:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str,
                 session=None) -> None:
        self._app = (client_id, client_secret)
        self._refresh_token = refresh_token
        self._session = session or requests.Session()

    def _report(self, token: str, start: date, end: date, **params: str) -> list[dict]:
        resp = self._session.get(REPORTS_URL, timeout=_TIMEOUT,
                                 headers={"Authorization": f"Bearer {token}"},
                                 params={"ids": "channel==MINE", "startDate": start.isoformat(),
                                         "endDate": end.isoformat(), **params})
        if resp.status_code != 200:
            raise AnalyticsApiError(f"reports.query HTTP {resp.status_code}: {_reason(resp)}")
        return rows_as_dicts(resp.json())

    def collect(self, today: date) -> dict:
        token = refresh_access_token(*self._app, self._refresh_token, session=self._session)
        start, end = window(today)
        videos = self._report(token, start, end, dimensions="video", metrics=_METRICS,
                              sort="-subscribersGained", maxResults="200")
        daily = self._report(token, start, end, dimensions="day", metrics=_METRICS)
        traffic = self._report(token, start, end, dimensions="day,insightTrafficSourceType",
                               metrics="views,estimatedMinutesWatched")
        for row in traffic:
            row["source_type"] = row.pop("insightTrafficSourceType")
        for row in videos:
            row["video_id"] = row.pop("video")
        return {"window_end": end, "window_days": WINDOW_DAYS,
                "videos": videos, "daily": daily, "traffic": traffic}
