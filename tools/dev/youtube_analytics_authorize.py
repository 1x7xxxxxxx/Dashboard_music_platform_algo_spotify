#!/usr/bin/env python3
"""Mint and store an artist's YouTube Analytics refresh_token (R511).

Type: Utility
Uses: Google OAuth 2.0 (authorization_code, PKCE, loopback redirect), YouTube Data API
      channels.list(mine=true)
Depends on: GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET (env), FERNET_KEY + the
            database for --store
Persists in: artist_credentials (platform 'youtube_analytics') — --store only

Two halves, joined by a pipe, so the token is NEVER printed on a terminal:

  python3 tools/dev/youtube_analytics_authorize.py \\
    | ssh root@<prod> 'cd /opt/streamlytics && docker compose exec -T airflow-scheduler \\
        python3 tools/dev/youtube_analytics_authorize.py --store --artist-id N'

1. Without --store (on the admin's machine, where the browser is): opens Google's consent
   page; the ARTIST signs in with the Google account that owns the channel; the refresh
   token is written to stdout — refused when stdout is a terminal.
2. With --store (where the database is): reads the token on stdin, asks Google which
   channel it opens (channels?mine=true), and REFUSES unless it is the channel_id the
   artist declared for YouTube — a token for someone else's channel would file their
   figures under this tenant. Then stores it encrypted. Runbook: runbook-actions-
   utilisateur.md, « YouTube Analytics ».
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import secrets
import sys
import time
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.collectors.youtube_analytics_collector import (  # noqa: E402
    SCOPES, TOKEN_URL, refresh_access_token,
)
from src.utils.env_files import load_project_env  # noqa: E402

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
REDIRECT = "http://127.0.0.1:8765/"
_result: dict = {}


def _app() -> tuple[str, str]:
    cid = (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
    secret = (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()
    if not cid or not secret:
        sys.exit("❌ GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET absent de l'environnement.")
    return cid, secret


def _handler(state: str):
    class _H(BaseHTTPRequestHandler):
        def log_message(self, *a) -> None:
            pass

        def do_GET(self) -> None:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in q or "error" in q:
                _result.update({k: v[0] for k, v in q.items()})
            ok = _result.get("code") and _result.get("state") == state
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(("✅ Autorisé — retour au terminal." if ok else "…").encode())
    return _H


def authorization_url(client_id: str, challenge: str, state: str) -> str:
    return AUTHORIZE_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state})


def _capture(client_id: str, challenge: str, state: str) -> str:
    server = HTTPServer(("127.0.0.1", 8765), _handler(state))
    server.timeout = 1
    url = authorization_url(client_id, challenge, state)
    print(f"Ouvre cette adresse, et fais-y connecter l'ARTISTE :\n  {url}\n", file=sys.stderr)
    webbrowser.open(url)
    deadline = time.time() + 300
    try:
        while "code" not in _result and "error" not in _result and time.time() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if _result.get("error") or not _result.get("code"):
        sys.exit(f"❌ pas de code d'autorisation ({_result.get('error', 'délai de 300 s')}).")
    if _result.get("state") != state:
        sys.exit("❌ state différent — rappel périmé ou forgé. Abandon.")
    return _result["code"]


def mint() -> int:
    if sys.stdout.isatty():
        sys.exit("❌ le jeton ne s'affiche pas : tube la sortie vers « --store » (voir l'aide).")
    cid, secret = _app()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    code = _capture(cid, challenge, secrets.token_urlsafe(24))
    resp = requests.post(TOKEN_URL, timeout=30, data={
        "code": code, "client_id": cid, "client_secret": secret, "redirect_uri": REDIRECT,
        "grant_type": "authorization_code", "code_verifier": verifier})
    token = resp.json().get("refresh_token") if resp.status_code == 200 else None
    if not token:
        sys.exit(f"❌ échange refusé : HTTP {resp.status_code}.")
    sys.stdout.write(token + "\n")
    print("✅ jeton obtenu, transmis au --store.", file=sys.stderr)
    return 0


def owned_channel(access_token: str, session=requests) -> str:
    resp = session.get(CHANNELS_URL, timeout=30, params={"part": "id", "mine": "true"},
                       headers={"Authorization": f"Bearer {access_token}"})
    items = (resp.json().get("items") or []) if resp.status_code == 200 else []
    if len(items) != 1:
        sys.exit(f"❌ ce compte Google n'ouvre pas exactement une chaîne (HTTP {resp.status_code}).")
    return items[0]["id"]


def store(artist_id: int, refresh_token: str, session=requests) -> int:
    from src.utils.credential_loader import load_platform_credentials, store_platform_secrets
    declared = (load_platform_credentials(artist_id, "youtube").get("channel_id") or "").strip()
    if not declared:
        sys.exit(f"❌ l'artiste {artist_id} n'a déclaré aucune chaîne YouTube : rien à comparer.")
    channel = owned_channel(refresh_access_token(*_app(), refresh_token, session=session),
                            session=session)
    if channel != declared:
        sys.exit(f"❌ ce jeton ouvre la chaîne {channel}, l'artiste {artist_id} a déclaré "
                 f"{declared}. Rien n'est enregistré.")
    store_platform_secrets(artist_id, "youtube_analytics", {"refresh_token": refresh_token},
                           {"channel_id": channel, "expired_at": None,
                            "authorized_at": datetime.now(timezone.utc).isoformat(
                                timespec="milliseconds")})
    print(f"✅ YouTube Analytics autorisé pour l'artiste {artist_id} (chaîne {channel}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store", action="store_true", help="read the token on stdin and store it")
    ap.add_argument("--artist-id", type=int, help="required with --store")
    args = ap.parse_args(argv)
    load_project_env()
    if not args.store:
        return mint()
    if args.artist_id is None:
        ap.error("--store needs --artist-id")
    token = sys.stdin.readline().strip()
    if not token:
        sys.exit("❌ aucun jeton reçu sur l'entrée standard.")
    return store(args.artist_id, token)


if __name__ == "__main__":
    sys.exit(main())
