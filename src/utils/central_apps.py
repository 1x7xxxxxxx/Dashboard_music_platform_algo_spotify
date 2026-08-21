"""Do the SHARED, admin-owned apps still authenticate? (ADR-006 central model)

Type: Utility
Uses: requests (direct platform auth endpoints), env vars
Depends on: nothing in this repo
Persists in: nothing

This logic used to live only in `tools/check_central_apps.py`, and `tools/` is not
on the import path inside the Airflow containers — measured in production on
2026-08-21, where the nightly check reported "No module named 'tools'" instead of
the broken Meta token it exists to find. `src/` is mounted everywhere, so the
probes live here and the CLI is a thin shell over them.

streaMLytics uses ONE admin-owned app per platform. An expired or misconfigured
central app blanks EVERY tenant at once, which is why this is checked one level
above the per-tenant credential checks. A platform whose env vars are absent is
skipped — not configured is not the same as broken.
"""
from __future__ import annotations

import os

import requests

from src.utils.meta_token_format import token_format_problem

TIMEOUT = 10

def _result(ok: bool, platform: str, reason: str = "") -> bool:
    if ok:
        print(f"✅ {platform} central app OK")
    else:
        print(f"❌ {platform}: {reason}")
    return ok


def check_spotify() -> bool:
    cid = os.getenv("SPOTIFY_CLIENT_ID")
    secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not (cid and secret):
        print("⚠️ Spotify: env not set")
        return True
    try:
        resp = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(cid, secret),
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        token = resp.json().get("access_token") if resp.ok else None
        if token:
            return _result(True, "Spotify")
        return _result(False, "Spotify", f"HTTP {resp.status_code} no access_token")
    except requests.RequestException as exc:
        return _result(False, "Spotify", str(exc))


def check_youtube() -> bool:
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        print("⚠️ YouTube: env not set")
        return True
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/i18nLanguages",
            params={"part": "snippet", "key": key},
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        items = resp.json().get("items") if resp.ok else None
        if resp.status_code == 200 and items:
            return _result(True, "YouTube")
        return _result(False, "YouTube", f"HTTP {resp.status_code} no items")
    except requests.RequestException as exc:
        return _result(False, "YouTube", str(exc))


def check_soundcloud() -> bool:
    cid = os.getenv("SOUNDCLOUD_CLIENT_ID")
    secret = os.getenv("SOUNDCLOUD_CLIENT_SECRET")
    if not (cid and secret):
        print("⚠️ SoundCloud: env not set")
        return True
    try:
        resp = requests.post(
            "https://api.soundcloud.com/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": cid,
                "client_secret": secret,
            },
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        token = resp.json().get("access_token") if resp.ok else None
        if token:
            return _result(True, "SoundCloud")
        return _result(False, "SoundCloud", f"HTTP {resp.status_code} no access_token")
    except requests.RequestException as exc:
        return _result(False, "SoundCloud", str(exc))


def check_meta() -> bool:
    """NON-FATAL by design. Meta System User tokens cannot be reliably validated via raw
    Graph REST (/me and /debug_token return code-190 "Malformed access token" for tokens
    that nonetheless work through the facebook_business SDK — observed in prod). So a
    confirmed-valid token prints ✅; anything else prints ⚠️ (inconclusive, NOT a failure)
    and returns True — the authoritative Meta signal is whether meta_ads_api_daily actually
    pulled rows (per-tenant silent-0-row monitoring), not this probe."""
    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        print("⚠️ Meta: env not set")
        return True

    # Shape before network. A malformed token answers `Malformed access token`
    # (code 190), which reads as "expired" and sends you regenerating instead of
    # looking at the string. The production value carried ONE stray leading
    # character for weeks (2026-08-21). This is the only Meta check that can be
    # conclusive, so unlike the REST probe below it is FATAL.
    problem = token_format_problem(token)
    if problem:
        print(f"❌ Meta: META_ACCESS_TOKEN is malformed — {problem}. "
              # 4 chars: enough to show the shape, short enough to carry no secret.
              f"Stored prefix: {token[:4]!r} (a Meta token starts with 'EAA'). "
              "No Graph call can succeed until this is fixed; do not regenerate "
              "before checking the value itself.")
        return False
    app_id, secret = os.getenv("META_APP_ID"), os.getenv("META_APP_SECRET")
    try:
        if app_id and secret:
            resp = requests.get(
                "https://graph.facebook.com/v21.0/debug_token",
                params={"input_token": token, "access_token": f"{app_id}|{secret}"},
                timeout=TIMEOUT,
                allow_redirects=False,
            )
            try:
                body = resp.json()
            except ValueError:
                body = {}
            if (body.get("data") or {}).get("is_valid"):
                return _result(True, "Meta")
            reason = (body.get("error") or {}).get("message") or f"HTTP {resp.status_code}"
            print(f"⚠️ Meta: REST validation inconclusive ({reason}) — normal for System User "
                  "tokens; confirm via meta_ads_api_daily row counts.")
            return True
        print("⚠️ Meta: set META_APP_ID/SECRET to attempt a debug_token check; otherwise "
              "confirm via meta_ads_api_daily row counts.")
        return True
    except requests.RequestException as exc:
        print(f"⚠️ Meta: probe error ({exc}) — confirm via meta_ads_api_daily row counts.")
        return True


# Env vars each central app needs to exist at all. Used by --require.
_REQUIRED_ENV = {
    "Spotify": ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"),
    "YouTube": ("YOUTUBE_API_KEY",),
    "SoundCloud": ("SOUNDCLOUD_CLIENT_ID", "SOUNDCLOUD_CLIENT_SECRET"),
    "Meta": ("META_ACCESS_TOKEN", "META_APP_ID", "META_APP_SECRET"),
}


def check_all_configured() -> bool:
    """Every central app must be PRESENT, not merely not-failing.

    The default mode skips a platform whose env vars are absent and still exits 0.
    That is right for a partial deployment — and exactly what let "all credentials
    failed" reach a beta artist: the container was missing the shared app entirely
    and nothing said so. Before inviting anyone, absent is red.
    """
    missing = {
        platform: [var for var in variables if not os.getenv(var)]
        for platform, variables in _REQUIRED_ENV.items()
    }
    missing = {p: v for p, v in missing.items() if v}
    for platform, variables in missing.items():
        print(f"❌ {platform} central app NOT configured — missing {', '.join(variables)}")
    return not missing
