"""The one place that writes a tenant's platform identity. Spotify lives in TWO tables.

Type: Utility
Uses: PostgresHandler
Triggers: the credentials form (src/dashboard/views/credentials/_render.py) and
    tools/create_canary.py
Persists in: artist_credentials.extra_config, saas_artists.spotify_artist_id

Why this module exists — measured 2026-08-21.

A tenant's Spotify artist id is stored in two places: `artist_credentials.extra_config`
(what the readiness checks and the credentials form read) and the
`saas_artists.spotify_artist_id` column (what `spotify_api_daily` reads to decide whose
catalogue to collect). The credentials form wrote both. `tools/create_canary.py` wrote
only the first.

The result was a tenant that reported "Connecte -- artiste << Daft Punk >> OK" on every
screen, passed its connection test, and collected NOTHING: the DAG succeeded in half a
second logging "aucun spotify_artist_id declare". A green that means nothing is worse
than a red -- and it happened to the canary, the tenant whose whole job is to catch
exactly this.

The duplication itself is the defect; collapsing the two columns is a migration, not a
bugfix. Until then, every writer goes through here, so no third writer can get it half
right.
"""

from __future__ import annotations

import json

# platform -> the key inside extra_config that carries the tenant's own identity.
IDENTITY_KEYS = {
    "spotify": "spotify_artist_id",
    "youtube": "channel_id",
    "soundcloud": "user_id",
    "meta": "account_id",
    "instagram": "ig_user_id",
}

# Platforms whose identity is ALSO mirrored on a saas_artists column, and where.
# A mirror that only one writer knows about is how the canary went green on nothing.
IDENTITY_MIRRORS = {
    "spotify": "spotify_artist_id",
}


def write_platform_identity(db, artist_id: int, platform: str, extra: dict) -> None:
    """Persist `extra` for this tenant AND every mirror the platform declares.

    Callers must already have validated the identity (ownership conflict, non-empty).
    """
    if platform not in IDENTITY_KEYS:
        raise ValueError(f"unknown platform {platform!r}; known: {sorted(IDENTITY_KEYS)}")

    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, %s, %s::jsonb) "
        "ON CONFLICT (artist_id, platform) DO UPDATE SET "
        "extra_config = COALESCE(artist_credentials.extra_config, '{}'::jsonb) "
        "|| EXCLUDED.extra_config, updated_at = CURRENT_TIMESTAMP",
        (artist_id, platform, json.dumps(extra)),
    )
    mirror_col = IDENTITY_MIRRORS.get(platform)
    if mirror_col:
        value = extra.get(IDENTITY_KEYS[platform]) or None
        # Identifier interpolated from a module-level constant, never from input
        # (cross-cutting rule #8); the value stays parameterised.
        assert mirror_col in set(IDENTITY_MIRRORS.values())
        db.execute_query(
            f"UPDATE saas_artists SET {mirror_col} = %s WHERE id = %s",  # noqa: S608
            (value, artist_id),
        )


def mirrored_columns() -> dict[str, str]:
    """Exposed so a test can assert every writer covers the same mirrors."""
    return dict(IDENTITY_MIRRORS)
