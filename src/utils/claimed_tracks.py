"""Tracks an artist owns that live on somebody else's profile.

Type: Utility
Uses: track_platform_link (existing table), SoundCloud resolve API
Triggers: the credentials SoundCloud tab, src/collectors/soundcloud_api_collector.py
Persists in: track_platform_link (platform_ref_id = the track id on that platform)

Why — 2026-08-22, the GRiNCH case.

An artist whose music is released by a label or a collective has nothing on their own
profile. Measured: `soundcloud.com/grinchhh` returns `track_count=0`, so his identity
is correct, his connection test is green on the account, and there is genuinely
nothing to collect. Every surface said "connecté, aucune donnée" and pointed at the
User ID, which was never the problem.

The unit of identity for such an artist is not the PROFILE, it is the TRACK. And that
works: `GET /tracks/{id}` returns `playback_count`, `reposts_count` and
`comment_count` whatever profile hosts the track — verified against a third party's
upload (1027 plays).

Nothing new is stored. `track_platform_link` already holds
`(artist_id, match_key, platform, platform_title, platform_ref_id, status, method)`,
and `platform_ref_id` is precisely "the id of this track on this platform". A claim is
one row with `method='manual'` and `status='confirmed'`; migration 074 makes such a
row exclusive, because two artists on one label would otherwise each collect the
other's plays under their own `artist_id`.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_SC_URL = re.compile(r"^https?://(?:www\.|m\.)?soundcloud\.com/[\w\-]+/[\w\-]+", re.I)


class TrackAlreadyClaimedError(RuntimeError):
    """Another tenant already owns this track. Never silently re-assign it."""


def is_soundcloud_track_url(value: str) -> bool:
    """A profile URL has one path segment; a track URL has two. Only tracks qualify."""
    return bool(_SC_URL.match((value or "").strip()))


def claimed_track_ids(db, artist_id: int, platform: str = "soundcloud") -> list[str]:
    """The platform track ids this tenant has claimed. Ordered, deduplicated."""
    rows = db.fetch_query(
        "SELECT DISTINCT platform_ref_id FROM track_platform_link "
        "WHERE artist_id = %s AND platform = %s AND method = 'manual' "
        "  AND status = 'confirmed' AND platform_ref_id IS NOT NULL "
        "  AND platform_ref_id <> '' ORDER BY 1",
        (artist_id, platform),
    )
    return [r[0] for r in rows]


def owner_of_claim(db, platform: str, platform_ref_id: str):
    """Which tenant already claimed this track, or None."""
    rows = db.fetch_query(
        "SELECT artist_id FROM track_platform_link "
        "WHERE platform = %s AND platform_ref_id = %s AND method = 'manual' "
        "  AND status = 'confirmed' LIMIT 1",
        (platform, str(platform_ref_id)),
    )
    return rows[0][0] if rows else None


def claim_track(db, artist_id: int, platform: str, platform_ref_id: str,
                title: str) -> None:
    """Record that `artist_id` owns this track. Refuses a track someone else claimed.

    The refusal is the point, and it is checked in code as well as by the partial
    unique index from migration 074: the index is the backstop, this is the message.
    """
    ref = str(platform_ref_id)
    owner = owner_of_claim(db, platform, ref)
    if owner is not None and owner != artist_id:
        raise TrackAlreadyClaimedError(
            f"le titre {platform}/{ref} est déjà revendiqué par un autre compte. "
            "Un titre n'appartient qu'à un artiste — sinon chacun collecterait les "
            "écoutes de l'autre."
        )
    if owner == artist_id:
        return
    db.execute_query(
        "INSERT INTO track_platform_link "
        "  (artist_id, match_key, platform, platform_title, platform_ref_id, "
        "   status, confidence, method) "
        "VALUES (%s, %s, %s, %s, %s, 'confirmed', 1.0, 'manual')",
        (artist_id, _match_key(title), platform, title[:200], ref),
    )


def release_claim(db, artist_id: int, platform: str, platform_ref_id: str) -> None:
    """Drop one claim. Scoped to the owner — a tenant cannot release another's."""
    db.execute_query(
        "DELETE FROM track_platform_link WHERE artist_id = %s AND platform = %s "
        "AND platform_ref_id = %s AND method = 'manual'",
        (artist_id, platform, str(platform_ref_id)),
    )


def _match_key(title: str) -> str:
    """The canonical join key this repo already uses for cross-platform titles.

    Reuses `track_matching.canonical_song` rather than inventing a second
    normalisation — the class `song-name-convention-mismatch` is exactly what happens
    when two places normalise a title their own way.
    """
    try:
        from src.utils.track_matching import canonical_song
        return (canonical_song(title) or title or "")[:200]
    except Exception:  # noqa: BLE001 — a claim must not fail on a helper import
        return (title or "")[:200]
