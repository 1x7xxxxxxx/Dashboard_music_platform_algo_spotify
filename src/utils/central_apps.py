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


# None of these probes surfaces the exception itself. YouTube passes its key
# in the query string, so a requests exception message embeds it; Spotify and
# SoundCloud use a header and a POST body and are clean today — but the rule
# is uniform on purpose, so nobody has to re-derive which one is safe.
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
        return _result(False, "Spotify", type(exc).__name__)


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
        return _result(False, "YouTube", type(exc).__name__)


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
        return _result(False, "SoundCloud", type(exc).__name__)


def check_meta() -> bool:
    """Mostly conclusive — and the part that is not is narrower than it used to be.

    This docstring used to state that "Meta System User tokens cannot be reliably
    validated via raw Graph REST", and that belief is what kept the probe advisory
    for months. It was wrong, and it was wrong for an instructive reason: the
    observation behind it (`/debug_token` returning code-190) came from a period
    when META_APP_ID held an AD ACCOUNT id, so `debug_token` was being called with
    app credentials that did not identify any app. The failure was read as a
    limitation of Graph rather than as a broken configuration, and a one-off
    observation was promoted into a general rule that then protected the defect.

    Measured 2026-08-21 with correct app credentials: `debug_token` validates a
    System User token perfectly — is_valid, type=SYSTEM_USER, expires_at=0, 43
    scopes. The probe is therefore authoritative when the app credentials work.

    What remains FATAL (conclusive):
      * a malformed token shape;
      * app credentials that Graph rejects.
    What remains ADVISORY: an unexpected debug_token payload, where the
    authoritative signal stays whether meta_ads_api_daily actually pulled rows.
    """
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

    # The APP credentials are conclusive on their own, and they were the real
    # blocker for weeks (2026-08-21): META_APP_ID held the AD ACCOUNT id
    # (567214713853881) instead of the APP id (2200684950508458). Both are plain
    # numbers of similar length, they live in different sections of Business
    # Manager, and nothing in the payload distinguishes them — so the failure read
    # as "the token expired" and three separate investigations went to the token.
    #
    # Graph tells the two apart precisely, and the two messages mean different
    # things. Naming them here is what turns a week into a minute:
    #   "Cannot get application info"        -> no app under that id (wrong id)
    #   "Invalid OAuth access token signature" -> app found, secret does not match
    if app_id and secret:
        try:
            resp = requests.get(
                f"https://graph.facebook.com/v21.0/{app_id}",
                params={"fields": "id,name", "access_token": f"{app_id}|{secret}"},
                timeout=TIMEOUT, allow_redirects=False)
            body = resp.json() if resp.content else {}
        except (requests.RequestException, ValueError) as e:
            # Same reason as above: the message would carry the app secret from the
            # query string. The [:120] truncation below happens to cut before it
            # today, which is luck, not a control.
            body = {"error": {"message": f"unreachable: {type(e).__name__}"}}
        app_err = (body.get("error") or {}).get("message", "")
        if app_err:
            hint = ""
            if "Cannot get application info" in app_err:
                hint = (" — no app exists under this id. An APP id is NOT an AD "
                        "ACCOUNT id: check Business Settings > Accounts > Apps, not "
                        "> Ad accounts. This exact confusion cost weeks of silent "
                        "non-collection.")
            elif "signature" in app_err.lower():
                hint = (" — the app is recognised but META_APP_SECRET does not match "
                        "it. Reset it in developers.facebook.com > Settings > Basic.")
            print(f"❌ Meta: app credentials rejected — {app_err[:120]}{hint}")
            return False

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
        # `type(exc).__name__`, never the exception itself. This request carries
        # META_ACCESS_TOKEN and `META_APP_ID|META_APP_SECRET` as QUERY PARAMETERS,
        # and a requests exception message embeds the full prepared URL — so
        # printing it wrote both secrets, in clear, into the Airflow task log that
        # `alert_monitor.check_central_apps` runs every night. No attacker needed:
        # one DNS blip or Graph outage was enough. Measured 2026-08-22.
        print(f"⚠️ Meta: probe error ({type(exc).__name__}) — "
              f"confirm via meta_ads_api_daily row counts.")
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
    missing = missing_central_env()
    for platform, variables in missing.items():
        print(f"❌ {platform} central app NOT configured — missing {', '.join(variables)}")
    return not missing


def missing_central_env(scope: set | None = None) -> dict:
    """{platform: [absent env vars]} — the DATA behind check_all_configured().

    Split out because the nightly monitor needs to SAY what is missing, not merely
    learn that something is. Until 2026-08-22 `alert_monitor.check_central_apps`
    called the bare probes, which return True on absent env by design ("not
    configured is not the same as broken" — correct for a partial deployment, wrong
    for a production check). The one condition that actually reached a beta artist —
    the shared app simply not wired into the container — was the one the nightly
    alert could not see.

    `scope` narrows to specific platforms: a scoped preflight must still prove that
    what it claims to prove is configured, rather than skipping the question.
    """
    wanted = {p.lower() for p in scope} if scope else None
    out = {}
    for platform, variables in _REQUIRED_ENV.items():
        if wanted is not None and platform.lower() not in wanted:
            continue
        absent = [var for var in variables if not os.getenv(var)]
        if absent:
            out[platform] = absent
    return out
