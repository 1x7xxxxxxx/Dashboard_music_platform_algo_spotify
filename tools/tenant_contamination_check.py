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


# ── What this tool considers, and how that set is decided ───────────────────
#
# Until 2026-08-22 the list below was eight table names, typed by hand. Five of the
# eight carried no platform identifier, so only the ORPHAN half applied to them, and
# there was NO Spotify entry at all — while `tracks` is the one table where a
# mismatch is provable, since it stores the Spotify artist id next to the tenant.
# Meanwhile the schema holds ~30 `meta_*` tables and the tool knew two of them.
#
# A hand-written scope on a growing schema is a check that shrinks every time
# someone adds a table, and says nothing when it does. So the set is DERIVED: each
# platform declares a table prefix, and every base table matching it that carries a
# tenant column is scanned. `tests/test_contamination_scope_is_derived.py` fails if
# a tenant-scoped table matches no platform and is not listed as deliberately out of
# scope, which is the part that cannot be forgotten.
#
# platform → {
#   "key":      identity field in artist_credentials.extra_config (or a saas_artists
#               column, for spotify),
#   "prefixes": table-name prefixes owned by this platform,
#   "ids":      {table: identifier column} — enables the MISMATCH check, which names
#               the real owner. Tables absent from this map get ORPHAN only.
#   "tenant":   {table: tenant column} — defaults to artist_id. On `tracks` the
#               tenant is `saas_artist_id` and `artist_id` is the SPOTIFY id
#               (.claude/rules/python.md: reason on the TYPE, never the name).
# }
_PLATFORMS = {
    "youtube": {
        "key": "channel_id",
        "prefixes": ("youtube_",),
        "ids": {"youtube_videos": "channel_id", "youtube_channels": "channel_id",
                "youtube_channel_history": "channel_id"},
        "tenant": {},
    },
    "instagram": {
        "key": "ig_user_id",
        "prefixes": ("instagram_",),
        "ids": {"instagram_daily_stats": "ig_user_id"},
        "tenant": {},
    },
    "soundcloud": {
        "key": "user_id",
        "prefixes": ("soundcloud_",),
        "ids": {},
        "tenant": {},
    },
    "meta": {
        "key": "account_id",
        "prefixes": ("meta_",),
        "ids": {},
        "tenant": {},
    },
    # The entry that did not exist. `tracks` pins a Spotify artist id against the
    # tenant that holds the row, so a mismatch here is as strong as YouTube's.
    "spotify": {
        "key": "spotify_artist_id",
        "prefixes": ("tracks", "track_popularity_history"),
        "ids": {"tracks": "artist_id"},
        "tenant": {"tracks": "saas_artist_id"},
    },
}

# Tenant-scoped tables that are deliberately NOT platform data. Each needs a reason,
# because "not listed" and "not applicable" must not look the same to the next reader.
_OUT_OF_SCOPE = {
    # Our own records about the tenant, not data fetched under their identity.
    "saas_users": "the tenant's own login rows",
    "artist_credentials": "the identity declarations this tool reads",
    "artist_subscriptions": "billing, written by Stripe webhooks",
    "subscription_plan_history": "billing history",
    "promo_events": "billing",
    "referral_codes": "billing",
    "active_sessions": "liveness heartbeats",
    "usage_events": "first-party analytics",
    "csv_upload_log": "audit trail of uploads",
    "etl_run_log": "pipeline telemetry",
    "etl_circuit_breaker": "pipeline telemetry",
    "artist_wrapped": "derived from the tenant's own data",
    "tenant_platform_probe": "our own record of what a platform answered us — not "
                             "data fetched under the tenant's identity",
    # CSV/manual sources: the tenant is stamped at upload time from the session, not
    # resolved from a platform identity, so there is no identity to compare against.
    "apple_daily_plays": "Apple Music CSV upload",
    "apple_listeners": "Apple Music CSV upload",
    "apple_songs_history": "Apple Music CSV upload",
    "apple_songs_performance": "Apple Music CSV upload",
    "distrokid_monthly_revenue": "distributor CSV upload",
    "distrokid_sales_detail": "distributor CSV upload",
    "imusician_monthly_revenue": "distributor CSV upload",
    "imusician_release_summary": "distributor CSV upload",
    "imusician_sales_detail": "distributor CSV upload",
    "sacem_statement": "SACEM statement upload",
    "hypeddit_campaigns": "Hypeddit CSV upload",
    "hypeddit_daily_stats": "Hypeddit CSV upload",
    "s4a_artist_radio_count": "Spotify for Artists CSV upload",
    "s4a_audience": "Spotify for Artists CSV upload",
    "s4a_song_algo_outcomes": "manual capture in the dashboard",
    "s4a_song_discovery_mode": "Spotify for Artists CSV upload",
    "s4a_song_nonalgo_streams": "Spotify for Artists CSV upload",
    "s4a_song_playlist_adds": "Spotify for Artists CSV upload",
    "s4a_song_playlists": "Spotify for Artists CSV upload",
    "s4a_song_saves_daily": "Spotify for Artists CSV upload",
    "s4a_song_timeline": "Spotify for Artists CSV upload",
    "s4a_songs_global": "Spotify for Artists CSV upload",
    # Derived from tables that ARE checked; contamination would be visible upstream.
    "ml_song_predictions": "derived from s4a_song_timeline",
    "ml_prediction_outcomes": "derived from ml_song_predictions",
    "campaign_mapping_rejected": "mapping decisions made in the dashboard",
    "campaign_track_mapping": "mapping decisions made in the dashboard",
    "track_platform_link": "mapping decisions made in the dashboard",
    "track_release_reference": "canonical release list, entered in the dashboard",
    # Shared Spotify catalogue: keyed by the Spotify artist id (VARCHAR), with no
    # tenant column at all. A row here is not owned by anyone.
    "artists": "shared Spotify catalogue, no tenant column (artist_id is a Spotify id)",
    "artist_history": "shared Spotify catalogue, no tenant column",
}

# Instagram identity lives in the `meta` credentials row (no row of its own).
_IDENTITY_PLATFORM = {"instagram": "meta"}


def tenant_scoped_tables(db) -> dict[str, str]:
    """{table: tenant column} for every base table carrying one, read from the schema.

    `tracks` carries both; `saas_artist_id` wins because it is the INTEGER one, and
    on that table `artist_id` is the Spotify identifier.
    """
    rows = db.fetch_query(
        "SELECT c.table_name, c.column_name, c.data_type "
        "FROM information_schema.columns c "
        "JOIN information_schema.tables t "
        "  ON t.table_name = c.table_name AND t.table_schema = c.table_schema "
        "WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE' "
        "  AND c.column_name IN ('artist_id', 'saas_artist_id')"
    )
    out: dict[str, str] = {}
    for table, column, dtype in rows:
        if column == "saas_artist_id":
            out[table] = column
        elif table not in out and dtype in ("integer", "bigint", "smallint"):
            out[table] = column
    return out


def platform_of(table: str) -> str | None:
    """Which platform owns this table, by prefix. None = not platform data."""
    for name, spec in _PLATFORMS.items():
        if any(table == p or table.startswith(p) for p in spec["prefixes"]):
            return name
    return None


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
        for name, spec in _PLATFORMS.items():
            key = spec["key"]
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
    artists = db.fetch_query("SELECT id, name FROM saas_artists ORDER BY id")
    scoped = tenant_scoped_tables(db)

    # Group the live schema by platform instead of trusting a typed list.
    by_platform: dict[str, list[tuple[str, str]]] = {}
    for table, tenant_col in sorted(scoped.items()):
        platform = platform_of(table)
        if platform is None:
            continue
        override = _PLATFORMS[platform]["tenant"].get(table)
        by_platform.setdefault(platform, []).append((table, override or tenant_col))

    findings: list[dict] = []
    for artist_id, name in artists:
        declared = identities.get(artist_id, {})
        for platform, tables in by_platform.items():
            identity = declared.get(platform)
            id_columns = _PLATFORMS[platform]["ids"]
            for table, tenant_col in tables:
                total = db.fetch_query(
                    f"SELECT COUNT(*) FROM {table} WHERE {tenant_col} = %s",
                    (artist_id,),
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

                id_column = id_columns.get(table)
                if not id_column:
                    continue
                bad = db.fetch_query(
                    f"SELECT {id_column}, COUNT(*) FROM {table} "
                    f"WHERE {tenant_col} = %s AND {id_column} <> %s "
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
    # took the column DEFAULT (1). Compare against the real owner via tracks — a
    # join, so it stays outside the per-table loop above.
    if "track_popularity_history" in scoped and "tracks" in scoped:
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

    # youtube_video_stats has no channel_id of its own; its owner is whatever
    # youtube_videos says. Same join shape, same reason it cannot sit in the loop.
    if "youtube_video_stats" in scoped and "youtube_videos" in scoped:
        rows = db.fetch_query(
            "SELECT s.artist_id, v.artist_id, COUNT(*) "
            "FROM youtube_video_stats s "
            "JOIN youtube_videos v ON v.video_id = s.video_id "
            "WHERE v.artist_id <> s.artist_id GROUP BY 1, 2 ORDER BY 3 DESC"
        )
        for holder, real_owner, count in rows:
            findings.append({
                "artist_id": holder, "artist": f"(holder {holder})",
                "platform": "youtube", "table": "youtube_video_stats",
                "kind": "MISATTRIBUTED", "rows": count,
                "detail": f"stats rows sit under {holder} while their video belongs "
                          f"to tenant {real_owner} (youtube_videos.artist_id)",
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
