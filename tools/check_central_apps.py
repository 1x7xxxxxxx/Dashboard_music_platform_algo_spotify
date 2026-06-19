#!/usr/bin/env python3
"""Authenticate each SHARED central app from env — catch expiry before a tenant does.

Type: Utility
Uses: requests (direct platform auth endpoints), env vars (central credential model, ADR-006)
Triggers: manual / CI run — `python3 tools/check_central_apps.py`

streaMLytics uses ONE admin-owned app per platform (ADR-006). An expired or
misconfigured central app blanks EVERY tenant at once. This probe authenticates
each configured central app directly so the failure is caught here, loudly,
instead of surfacing as "0 rows" per tenant. A platform whose env vars are
absent is skipped (not a failure); a CONFIGURED app that fails auth exits 1.
"""
import os
import sys

import requests

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
    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        print("⚠️ Meta: env not set")
        return True
    try:
        resp = requests.get(
            "https://graph.facebook.com/v21.0/me",
            params={"access_token": token},
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        meta_id = resp.json().get("id") if resp.ok else None
        if meta_id:
            return _result(True, "Meta")
        return _result(False, "Meta", f"HTTP {resp.status_code} no id")
    except requests.RequestException as exc:
        return _result(False, "Meta", str(exc))


def main() -> int:
    checks = (check_spotify, check_youtube, check_soundcloud, check_meta)
    # A skipped (env-absent) platform returns True; only a configured failure → False.
    ok = all(check() for check in checks)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
