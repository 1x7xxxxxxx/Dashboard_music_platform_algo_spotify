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
import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require", action="store_true",
        help="treat an absent central app as a failure (pre-flight before inviting "
             "an artist), instead of skipping it",
    )
    args = parser.parse_args()

    checks = (check_spotify, check_youtube, check_soundcloud, check_meta)
    # A skipped (env-absent) platform returns True; only a configured failure → False.
    # Evaluated eagerly: every platform is reported, not just the first failure.
    results = [check() for check in checks]
    ok = all(results)
    if args.require:
        ok = check_all_configured() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
