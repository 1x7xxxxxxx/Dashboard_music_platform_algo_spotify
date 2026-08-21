#!/usr/bin/env python3
"""Create the canary tenant — the one thing `make artist-preflight` cannot start without.

Type: Utility
Uses: PostgresHandler, the credentials registry (platform identity fields)
Triggers: `make canary ARTIST_NAME="…" [SPOTIFY=… YOUTUBE=… SOUNDCLOUD=… META=…]`
Persists in: saas_artists (one row, is_canary = TRUE) + artist_credentials

Roadmap item R20 said: "create a real, non-admin account whose platform identities
are yours but DIFFERENT from the admin's". Everything in that sentence except the
identities is mechanical — the row, the flag, the credential shape, the checks
that it really is distinct from the admin. This does that part, so what is left
for a human is choosing which of their public profiles to point at.

Why the identities are not defaulted, guessed, or copied from the admin: that is
the exact rule this repo spent two sessions enforcing after
`track_popularity_history` filed every tenant's history under artist 1. A canary
that borrows the admin's channel proves nothing — it would pass while the isolation
it exists to test is broken. So an identity equal to the admin's is refused here,
loudly.

Idempotent: re-running with the same slug updates the identities of the existing
canary rather than creating a second one.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# A shell has no .env; Docker does. Resolve it from the repo root so this tool is
# correct from any cwd, and so a red verdict below means "missing", not "unloaded".
from src.utils.env_files import load_project_env  # noqa: E402
from src.utils.tenant_identity import (  # noqa: E402
    mirrored_columns,
    write_platform_identity,
)

load_project_env()

_OK, _KO, _WARN = "✅", "❌", "⚠️"

# platform → the key the collectors read out of extra_config. Kept in step with
# `src/dashboard/views/credentials/_core.py::UNIQUE_IDENTITY_FIELDS`; the test below
# fails if a platform gains an identity field this tool cannot set.
_IDENTITY_FIELD = {
    "soundcloud": "user_id",
    "youtube": "channel_id",
    "meta": "account_id",
    "spotify": "spotify_artist_id",
}


def _connect():
    from src.database.postgres_handler import PostgresHandler

    return PostgresHandler.from_env_or_config()


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "canary"


def _admin_identities(db) -> dict[str, str]:
    """What the admin (artist 1) declares, so we can refuse to reuse it."""
    rows = db.fetch_query(
        "SELECT platform, extra_config FROM artist_credentials WHERE artist_id = 1")
    out: dict[str, str] = {}
    for platform, extra in rows or []:
        cfg = extra if isinstance(extra, dict) else json.loads(extra or "{}")
        field = _IDENTITY_FIELD.get(platform)
        if field and (cfg or {}).get(field):
            out[platform] = str(cfg[field]).strip()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Create (or update) the canary tenant used by `make artist-preflight`.")
    ap.add_argument("--name", required=True, help='Display name, e.g. "Canary — 1x7"')
    ap.add_argument("--slug", help="URL slug (default: derived from --name)")
    ap.add_argument("--tier", default="free", choices=["free", "premium"])
    for platform in _IDENTITY_FIELD:
        ap.add_argument(f"--{platform}", help=f"this tenant's own {_IDENTITY_FIELD[platform]}")
    ap.add_argument("--dry-run", action="store_true", help="say what would happen, write nothing")
    args = ap.parse_args()

    given = {p: (getattr(args, p) or "").strip() for p in _IDENTITY_FIELD}
    given = {p: v for p, v in given.items() if v}
    if not given:
        print(f"{_WARN} no platform identity given — the canary will exist but prove nothing.")
        print("    Pass at least one, e.g. --spotify <artist id> or --youtube UC…")

    db = _connect()
    try:
        admin = _admin_identities(db)
        clashes = [p for p, v in given.items() if admin.get(p) == v]
        if clashes:
            print(f"{_KO} identity identical to the admin's on: {', '.join(clashes)}.")
            print("    A canary that reuses the admin's identity passes while the")
            print("    isolation it exists to test is broken. Use a different profile.")
            return 1

        # Resolve the slug BEFORE the uniqueness check: re-running this tool with
        # the same slug and the same identities must be a no-op, not a refusal.
        # It was a refusal until it was tried — the canary was reported as the
        # tenant already claiming its own identity.
        slug = args.slug or _slugify(args.name)
        existing = db.fetch_query("SELECT id FROM saas_artists WHERE slug = %s", (slug,))
        self_id = existing[0][0] if existing else None

        taken = []
        for platform, value in given.items():
            field = _IDENTITY_FIELD[platform]
            rows = db.fetch_query(
                "SELECT artist_id FROM artist_credentials "
                "WHERE platform = %s AND extra_config->>%s = %s "
                "AND artist_id IS DISTINCT FROM %s",
                (platform, field, value, self_id))
            taken += [f"{platform}={value} (artist {r[0]})" for r in (rows or [])]
        if taken:
            print(f"{_KO} identity already claimed by another tenant: {'; '.join(taken)}.")
            print("    `find_identity_conflict()` refuses this in the form too (R30).")
            return 1
        if args.dry_run:
            verb = "update" if existing else "create"
            print(f"{_OK} dry-run: would {verb} canary slug={slug!r} "
                  f"with {len(given)} identity(ies): {', '.join(given) or 'none'}")
            return 0

        if existing:
            artist_id = existing[0][0]
            db.execute_query(
                "UPDATE saas_artists SET is_canary = TRUE, active = TRUE, name = %s "
                "WHERE id = %s", (args.name, artist_id))
            print(f"{_OK} canary already existed (slug={slug!r}) → artist_id={artist_id}, refreshed")
        else:
            artist_id = db.fetch_query(
                "INSERT INTO saas_artists (name, slug, tier, active, is_canary) "
                "VALUES (%s, %s, %s, TRUE, TRUE) RETURNING id",
                (args.name, slug, args.tier))[0][0]
            print(f"{_OK} canary created — artist_id={artist_id}, slug={slug!r}")

        for platform, value in given.items():
            field = _IDENTITY_FIELD[platform]
            # Through the shared writer: Spotify's identity is ALSO mirrored on
            # saas_artists.spotify_artist_id, which is what spotify_api_daily reads.
            # Writing only the credentials row produced a canary that passed every
            # screen and collected nothing (2026-08-21).
            write_platform_identity(db, artist_id, platform, {field: value})
            mirror = mirrored_columns().get(platform)
            print(f"   {_OK} {platform}: {field} = {value}"
                  + (f"  (+ saas_artists.{mirror})" if mirror else ""))

        print()
        print("Next: make artist-preflight       # proves this tenant end to end")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
