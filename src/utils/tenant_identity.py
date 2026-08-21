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
from typing import NamedTuple

class PlatformIdentity(NamedTuple):
    """How one logical platform's tenant identity is named and stored.

    `logical` and `storage` differ for exactly one platform, and conflating them is
    a real bug source: Instagram is a logical platform everywhere (readiness, the
    alert monitor, the connection tests) but its identity lives INSIDE the `meta`
    credentials row, because the artist types it in the Meta tab. Writing it under
    `platform='instagram'` would create a row no consumer reads -- the DAG selects
    tenants on `creds['meta']['ig_user_id']`.
    """

    logical: str
    storage: str
    field: str
    mirror: str | None


# THE registry. Five entries, and every other surface derives from it.
#
# Before 2026-08-22 this map existed in five places that disagreed: here (5 entries),
# `artist_readiness._PLATFORMS` (5), `credentials/_core.UNIQUE_IDENTITY_FIELDS` (4),
# `tools/create_canary._IDENTITY_FIELD` (4) and `tests/test_identity_fields_collectable`
# (5). The two 4-entry copies both omitted Instagram, so `find_identity_conflict`
# returned None for it -- two tenants could claim the same Instagram account in
# silence -- and the canary could not exercise the platform at all.
#
# What made it invisible: `tests/test_create_canary` asserted the tool EQUALLED the
# 4-entry copy, so a green guard held the gap in place; and
# `tests/test_identity_uniqueness` parametrised over that same copy, so the missing
# entry removed tests instead of failing one. A registry that its own guards derive
# from cannot report its own omission -- hence the literal ratchet in that file.
PLATFORM_IDENTITIES = {
    "soundcloud": PlatformIdentity("soundcloud", "soundcloud", "user_id", None),
    "spotify": PlatformIdentity("spotify", "spotify", "spotify_artist_id",
                                "spotify_artist_id"),
    "youtube": PlatformIdentity("youtube", "youtube", "channel_id", None),
    "meta": PlatformIdentity("meta", "meta", "account_id", None),
    # Rides the meta row. See PlatformIdentity's docstring.
    "instagram": PlatformIdentity("instagram", "meta", "ig_user_id", None),
}


def storage_platform(logical: str) -> str:
    """The `artist_credentials.platform` value that holds this identity."""
    spec = PLATFORM_IDENTITIES.get(logical)
    return spec.storage if spec else logical


def identity_field(logical: str) -> str | None:
    """The extra_config key carrying this platform's tenant identity."""
    spec = PLATFORM_IDENTITIES.get(logical)
    return spec.field if spec else None


def declared_identities(extra_by_platform: dict) -> set:
    """Logical platforms this tenant has actually DECLARED an identity for.

    Pure — no DB, no Streamlit. `extra_by_platform` is {storage_platform: extra_config}.

    Exists because four surfaces decided "connected" from the EXISTENCE of an
    `artist_credentials` row rather than from the identity value, so an artist who
    opened a tab and saved it blank was shown ✅ while readiness said ⚪. The Meta row
    made it worse: a row holding only `ig_user_id` counted as Meta-connected.
    """
    out = set()
    for logical, spec in PLATFORM_IDENTITIES.items():
        value = (extra_by_platform.get(spec.storage) or {}).get(spec.field)
        if str(value or "").strip():
            out.add(logical)
    return out


# Derived views, kept so existing callers and guards keep working unchanged.
# platform -> the key inside extra_config that carries the tenant's own identity.
IDENTITY_KEYS = {k: v.field for k, v in PLATFORM_IDENTITIES.items()}

# Platforms whose identity is ALSO mirrored on a saas_artists column, and where.
# A mirror that only one writer knows about is how the canary went green on nothing.
IDENTITY_MIRRORS = {k: v.mirror for k, v in PLATFORM_IDENTITIES.items() if v.mirror}


def write_platform_identity(db, artist_id: int, platform: str, extra: dict) -> None:
    """Persist `extra` for this tenant AND every mirror the platform declares.

    Callers must already have validated the identity (ownership conflict, non-empty).
    """
    if platform not in IDENTITY_KEYS:
        raise ValueError(f"unknown platform {platform!r}; known: {sorted(IDENTITY_KEYS)}")

    # The row is written under the STORAGE platform, never the logical one: an
    # `instagram` row would be an orphan nothing reads (the DAG selects tenants on
    # `creds['meta']['ig_user_id']`). The `||` merge below means the ig_user_id
    # composes with account_id in the meta row instead of clobbering it.
    #
    # `logical` is kept SEPARATE and used for every registry lookup after this
    # point. Reassigning `platform` in place would silently make the mirror lookup
    # ask about the storage row — correct today only by luck, since meta has no
    # mirror, and wrong the day a mirrored platform gains a different storage.
    logical = platform
    storage = storage_platform(logical)

    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, %s, %s::jsonb) "
        "ON CONFLICT (artist_id, platform) DO UPDATE SET "
        "extra_config = COALESCE(artist_credentials.extra_config, '{}'::jsonb) "
        "|| EXCLUDED.extra_config, updated_at = CURRENT_TIMESTAMP",
        (artist_id, storage, json.dumps(extra)),
    )
    mirror_col = IDENTITY_MIRRORS.get(logical)
    if mirror_col:
        value = extra.get(IDENTITY_KEYS[logical]) or None
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
