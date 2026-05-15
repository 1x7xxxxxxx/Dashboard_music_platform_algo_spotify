#!/usr/bin/env python3
"""
Type: Utility
Uses: SoundCloud OAuth 2.1 (authorization_code + PKCE)
Depends on: requests (project dep), stdlib only otherwise
Persists in: nothing — prints the refresh_token; you paste it into the dashboard

Mint the FIRST SoundCloud `refresh_token` (the one-time browser step the
dormant B2 P2 dual-mode collector cannot do itself). After this, the collector
auto-rotates/persists it every run.

Run:  python tools/dev/soundcloud_oauth_authorize.py \
          --client-id ... --client-secret ...
(or set SOUNDCLOUD_CLIENT_ID / SOUNDCLOUD_CLIENT_SECRET). Full runbook:
.claude/dev-docs/soundcloud-oauth-guide.md
"""
import argparse
import base64
import hashlib
import os
import secrets
import sys
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

# Same token endpoint the collector refreshes against — keeps the minted
# refresh_token consistent with src/collectors/soundcloud_api_collector.py.
_TOKEN_ENDPOINT = "https://api.soundcloud.com/oauth2/token"
_DEFAULT_REDIRECT = "http://localhost:8888/callback"
_DEFAULT_AUTHORIZE = "https://secure.soundcloud.com/authorize"

_result: dict = {}


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def _make_handler(expected_state: str, path: str):
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence default stderr noise
            pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(parsed.query)
            code = (q.get("code") or [None])[0]
            err = (q.get("error") or [None])[0]
            st = (q.get("state") or [None])[0]
            # Ignore anything that isn't the real callback (favicon, probes,
            # wrong path) so a stray request can't consume the one-shot.
            if parsed.path != path or (not code and not err):
                self.send_response(204)
                self.end_headers()
                return
            _result["code"], _result["error"], _result["state"] = code, err, st
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            ok = code and st == expected_state
            msg = "✅ SoundCloud authorized — return to the terminal." if ok \
                else "❌ Authorization failed — see terminal."
            self.wfile.write(msg.encode())

    return _Handler


def _capture_code(redirect_uri: str, authorize_url: str,
                  client_id: str, challenge: str, state: str) -> str:
    parts = urllib.parse.urlparse(redirect_uri)
    try:
        server = HTTPServer((parts.hostname, parts.port or 80),
                            _make_handler(state, parts.path or "/"))
    except OSError as e:
        sys.exit(f"❌ cannot bind {parts.hostname}:{parts.port} ({e}). "
                 "Close whatever uses that port or pass a free --redirect-uri "
                 "(must also be registered on the SoundCloud app).")
    server.timeout = 1  # handle_request returns each second so we can poll

    params = urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri,
        "response_type": "code", "code_challenge": challenge,
        "code_challenge_method": "S256", "state": state,
    })
    url = f"{authorize_url}?{params}"
    print(f"\nOpen this URL and authorize (also tried your browser):\n  {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print(f"Waiting for the redirect on {redirect_uri} … (Ctrl-C to abort)")

    deadline = time.time() + 300
    try:
        while ("code" not in _result and "error" not in _result
               and time.time() < deadline):
            server.handle_request()  # blocks ≤1s (server.timeout), then loops
    except KeyboardInterrupt:
        sys.exit("\n❌ Aborted.")
    finally:
        server.server_close()

    if _result.get("error"):
        sys.exit(f"❌ SoundCloud returned error: {_result['error']}")
    if not _result.get("code"):
        sys.exit("❌ Timed out (300s) waiting for the callback. Check that the "
                 "app's Redirect URI exactly matches and the port is free.")
    if _result.get("state") != state:
        sys.exit("❌ state mismatch — possible CSRF / stale callback. Aborting.")
    return _result["code"]


def _exchange(code: str, verifier: str, client_id: str,
              client_secret: str, redirect_uri: str) -> dict:
    r = requests.post(_TOKEN_ENDPOINT, data={
        "grant_type": "authorization_code", "client_id": client_id,
        "client_secret": client_secret, "redirect_uri": redirect_uri,
        "code_verifier": verifier, "code": code,
    }, timeout=20)
    if r.status_code != 200:
        sys.exit(f"❌ token exchange failed: HTTP {r.status_code} — "
                 f"{r.text[:300]}\n   (try --authorize-url "
                 "https://api.soundcloud.com/connect if the host is wrong)")
    return r.json()


def main() -> int:
    p = argparse.ArgumentParser(description="Mint a SoundCloud refresh_token (PKCE).")
    p.add_argument("--client-id", default=os.getenv("SOUNDCLOUD_CLIENT_ID"))
    p.add_argument("--client-secret", default=os.getenv("SOUNDCLOUD_CLIENT_SECRET"))
    p.add_argument("--redirect-uri", default=_DEFAULT_REDIRECT,
                   help="MUST exactly match a Redirect URI registered on the app")
    p.add_argument("--authorize-url", default=_DEFAULT_AUTHORIZE,
                   help="SoundCloud authorize host (varies by API version)")
    args = p.parse_args()

    if not args.client_id or not args.client_secret:
        print("❌ missing SOUNDCLOUD_CLIENT_ID / SOUNDCLOUD_CLIENT_SECRET "
              "(env or --client-id/--client-secret).", file=sys.stderr)
        return 2

    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(24)
    code = _capture_code(args.redirect_uri, args.authorize_url,
                         args.client_id, challenge, state)
    tok = _exchange(code, verifier, args.client_id,
                    args.client_secret, args.redirect_uri)

    rt = tok.get("refresh_token")
    if not rt:
        sys.exit(f"❌ no refresh_token in response: {tok}")
    print("\n✅ refresh_token obtained.\n")
    print(f"  refresh_token : {rt}")
    print(f"  access_token  : expires in {tok.get('expires_in', '?')}s\n")
    print("Next — verify it exposes real likes (GO/NO-GO):\n")
    print(f'  SOUNDCLOUD_CLIENT_ID="{args.client_id}" \\')
    print('  SOUNDCLOUD_CLIENT_SECRET="<secret>" \\')
    print('  SOUNDCLOUD_USER_ID="<your numeric user id>" \\')
    print(f'  SOUNDCLOUD_REFRESH_TOKEN="{rt}" \\')
    print("  python airflow/debug_dag/debug_soundcloud_oauth.py\n")
    print("If ✅ GO: Dashboard → Credentials → SoundCloud → paste it into "
          "'Refresh Token (OAuth, optionnel)'. The collector then auto-"
          "rotates & persists it (one-time mint).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
