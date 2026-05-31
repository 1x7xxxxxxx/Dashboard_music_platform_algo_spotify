#!/usr/bin/env python3
"""Inject a Meta System User token into artist_credentials without the dashboard.

Type: Utility (dev/ops, one-shot)
Uses: src.dashboard.views.credentials._core._get_fernet (same Fernet key/format as the app),
      PostgresHandler, config_loader
Persists in: artist_credentials (UPDATE token_encrypted + expires_at=NULL)

Why this exists: the dashboard Meta save path always tries to stamp an expires_at and,
for a never-expiring System User token (debug_token returns expires_at=0), leaves the
stale expiry in place. This injects the token cleanly: it decrypts the current blob to
PRESERVE app_secret, swaps only access_token, re-encrypts with the app's Fernet key, and
sets expires_at=NULL so meta_token_refresh skips it (Brick 24) and treats it as eternal.

Secret-safe: the token is read from a FILE you create (never from argv text or this chat).
Create the file with your editor (not `echo`, which would echo the secret), e.g. save the
token to /tmp/mtok.txt, then:

    python3 tools/dev/inject_meta_token.py /tmp/mtok.txt [--artist-id 1]

It prints no secret. Delete the token file afterwards (`shred -u /tmp/mtok.txt`).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.getcwd())

from src.dashboard.views.credentials._core import _get_fernet  # noqa: E402
from src.database.postgres_handler import PostgresHandler  # noqa: E402
from src.utils.config_loader import config_loader  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("token_file", help="Path to a file containing ONLY the Meta token")
    ap.add_argument("--artist-id", type=int, default=1)
    args = ap.parse_args()

    new_token = open(args.token_file, encoding="utf-8").read().strip()
    if not new_token or len(new_token) < 20:
        print("❌ Token file is empty or too short — aborting.", file=sys.stderr)
        return 1

    f = _get_fernet()
    if f is None:
        print("❌ FERNET_KEY not configured (env or config.yaml) — aborting.", file=sys.stderr)
        return 1

    c = config_loader.load().get("database", {})
    db = PostgresHandler(
        host=c.get("host", "localhost"), port=c.get("port", 5433),
        database=c.get("dbname") or c.get("database", "spotify_etl"),
        user=c.get("user", "postgres"), password=c.get("password"),
    )

    row = db.fetch_query(
        "SELECT token_encrypted FROM artist_credentials WHERE artist_id=%s AND platform='meta'",
        (args.artist_id,),
    )
    if not row or not row[0][0]:
        print(f"❌ No existing meta credential row for artist {args.artist_id}.", file=sys.stderr)
        return 1

    # Decrypt current blob to PRESERVE app_secret; swap only access_token.
    current = json.loads(f.decrypt(row[0][0].encode()).decode())
    had_secret = bool(current.get("app_secret"))
    current["access_token"] = new_token
    new_blob = f.encrypt(json.dumps(current).encode()).decode()

    db.execute_query(
        "UPDATE artist_credentials SET token_encrypted=%s, expires_at=NULL, updated_at=now() "
        "WHERE artist_id=%s AND platform='meta'",
        (new_blob, args.artist_id),
    )

    print(f"✅ Meta token updated for artist {args.artist_id}. "
          f"app_secret preserved: {had_secret}. expires_at set to NULL (System User).")
    print("   Delete the token file now:  shred -u " + args.token_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
