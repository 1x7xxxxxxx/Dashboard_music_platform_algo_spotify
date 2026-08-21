#!/usr/bin/env python3
"""Report rows that sit under a tenant they cannot belong to. READ-ONLY.

Type: Utility
Uses: PostgresHandler (via DATABASE_URL or config.yaml), artist_credentials, saas_artists
Triggers: `python3 tools/tenant_contamination_check.py` — manual, and step 5 of
    `make artist-preflight`
Persists in: nothing (this script never writes)

Two artist test sessions showed the ADMIN's data under the artist's account. The
code paths that caused it are fixed, but the rows they already wrote are still in
production. This tells you how many, per tenant and per platform, before anything
is deleted.

Two independent signals:

  MISMATCH — the row carries a platform identifier that is NOT the tenant's
             declared one (e.g. a youtube_videos row whose channel_id belongs to
             someone else). The strongest evidence: it names the real owner.

  ORPHAN   — the tenant has rows for a platform they never connected. Legitimate
             collection is impossible without an identity, so these rows were
             fetched under somebody else's.

Exit code 0 = clean, 1 = contaminated rows found, 2 = could not run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# A shell has no .env; Docker does. Resolve it from the repo root so this tool is
# correct from any cwd, and so a red verdict below means "missing", not "unloaded".
from src.utils.env_files import load_project_env  # noqa: E402

load_project_env()


def _connect():
    """The one resolution (R33): DATABASE_URL → DATABASE_* → config.yaml.

    This used to read DATABASE_URL then config.yaml only, skipping the env vars —
    which is exactly how Airflow is configured. So the tool worked from a dev
    machine and not from the container where the collectors run.
    """
    from src.database.postgres_handler import PostgresHandler

    return PostgresHandler.from_env_or_config()


# platform → (identity key in artist_credentials.extra_config,
#             [(table, identifier column or None)])
# A None column means the table carries no platform identifier, so only the
# ORPHAN check applies there.
_PLATFORMS = {
    "youtube": ("channel_id", [("youtube_videos", "channel_id"),
                               ("youtube_channels", "channel_id"),
                               ("youtube_video_stats", None)]),
    "instagram": ("ig_user_id", [("instagram_daily_stats", "ig_user_id"),
                                 ("instagram_media", None)]),
    "soundcloud": ("user_id", [("soundcloud_tracks_daily", None)]),
    "meta": ("account_id", [("meta_campaigns", None), ("meta_ads", None)]),
}

# Instagram identity lives in the `meta` credentials row (no row of its own).
_IDENTITY_PLATFORM = {"instagram": "meta"}


def _declared_identities(db) -> dict:
    """{artist_id: {platform: identity}} from artist_credentials + saas_artists."""
    out: dict[int, dict[str, str]] = {}
    rows = db.fetch_query(
        "SELECT artist_id, platform, extra_config FROM artist_credentials")
    for artist_id, platform, extra in rows:
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                extra = {}
        extra = extra or {}
        bucket = out.setdefault(artist_id, {})
        for name, (key, _) in _PLATFORMS.items():
            source = _IDENTITY_PLATFORM.get(name, name)
            if platform == source and (extra.get(key) or "").strip():
                bucket[name] = extra[key].strip()
    for artist_id, spotify_id in db.fetch_query(
            "SELECT id, spotify_artist_id FROM saas_artists "
            "WHERE spotify_artist_id IS NOT NULL AND spotify_artist_id <> ''"):
        out.setdefault(artist_id, {})["spotify"] = spotify_id
    return out


def _table_exists(db, table: str) -> bool:
    return bool(db.fetch_query(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %s", (table,)))


def scan(db) -> list[dict]:
    """Return one finding per (artist, table, kind). Never writes."""
    identities = _declared_identities(db)
    artists = db.fetch_query(
        "SELECT id, name FROM saas_artists ORDER BY id")
    findings: list[dict] = []

    for artist_id, name in artists:
        declared = identities.get(artist_id, {})
        for platform, (_key, tables) in _PLATFORMS.items():
            identity = declared.get(platform)
            for table, id_column in tables:
                if not _table_exists(db, table):
                    continue
                total = db.fetch_query(
                    f"SELECT COUNT(*) FROM {table} WHERE artist_id = %s", (artist_id,)
                )[0][0]
                if not total:
                    continue

                if not identity:
                    findings.append({
                        "artist_id": artist_id, "artist": name, "platform": platform,
                        "table": table, "kind": "ORPHAN", "rows": total,
                        "detail": "tenant never declared an identity for this platform",
                    })
                    continue

                if id_column:
                    bad = db.fetch_query(
                        f"SELECT {id_column}, COUNT(*) FROM {table} "
                        f"WHERE artist_id = %s AND {id_column} <> %s "
                        f"GROUP BY 1 ORDER BY 2 DESC",
                        (artist_id, identity),
                    )
                    for foreign_id, count in bad:
                        findings.append({
                            "artist_id": artist_id, "artist": name, "platform": platform,
                            "table": table, "kind": "MISMATCH", "rows": count,
                            "detail": f"rows carry {id_column}={foreign_id!r}, "
                                      f"tenant declared {identity!r}",
                        })

    # track_popularity_history: the payload had no artist_id at all, so every row
    # took the column DEFAULT (1). Compare against the real owner via tracks.
    if _table_exists(db, "track_popularity_history") and _table_exists(db, "tracks"):
        rows = db.fetch_query(
            "SELECT h.artist_id, t.saas_artist_id, COUNT(*) "
            "FROM track_popularity_history h "
            "JOIN tracks t ON t.track_id = h.track_id "
            "WHERE t.saas_artist_id IS NOT NULL AND t.saas_artist_id <> h.artist_id "
            "GROUP BY 1, 2 ORDER BY 3 DESC"
        )
        for holder, real_owner, count in rows:
            findings.append({
                "artist_id": holder, "artist": f"(holder {holder})",
                "platform": "spotify", "table": "track_popularity_history",
                "kind": "MISATTRIBUTED", "rows": count,
                "detail": f"rows belong to tenant {real_owner} "
                          f"(tracks.saas_artist_id) but are stored under {holder}",
            })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    try:
        db = _connect()
    except Exception as exc:  # noqa: BLE001 — a CLI reports, it does not crash
        print(f"❌ cannot connect: {exc}", file=sys.stderr)
        return 2

    try:
        findings = scan(db)
    finally:
        db.close()

    if args.json:
        print(json.dumps(findings, indent=2))
    elif not findings:
        print("✅ no cross-tenant contamination found")
    else:
        total = sum(f["rows"] for f in findings)
        print(f"⚠️  {len(findings)} finding(s), {total} row(s) under a tenant "
              "they cannot belong to\n")
        width = max(len(f["artist"]) for f in findings)
        for f in findings:
            print(f"  [{f['kind']:<13}] {f['artist']:<{width}} "
                  f"{f['platform']:<10} {f['table']:<26} {f['rows']:>7} rows")
            print(f"      {f['detail']}")
        print("\nNothing was modified. Review, back up (tools/db_backup.sh), then "
              "clean up deliberately.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
