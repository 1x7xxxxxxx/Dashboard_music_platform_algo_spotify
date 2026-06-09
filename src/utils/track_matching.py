"""Cross-platform track title matching + release-date reference.

Type: Utility
Uses: PostgresHandler (caller-provided — never opens its own connection)
Depends on: s4a_songs_global (source), track_release_reference (target)
Persists in: track_release_reference

The same track is spelled differently on each platform:
    S4A    "Je ne parle pas très bien le français - Remix"
    Apple  "Je ne parle pas très bien le français (Remix)"
    S4A    "Ca te dérange..."   Apple  "Ça te dérange..."   (accent)

`normalize_track_title` collapses these to a single match_key (accents stripped,
remix/original markers unified) so platform-local names can join to the canonical
release date held in `track_release_reference`. Remix and original keep DISTINCT
keys — they have distinct release dates.
"""
import logging
import re
import unicodedata
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Characters S4A replaces with '_' in export filenames (Windows-reserved set).
# s4a_song_timeline / ml_song_predictions are filename-derived (so they carry
# '_'), while CSV/API tables (s4a_songs_global, tracks, track_popularity_history,
# campaign_track_mapping) keep the real chars. canonical_song() bridges the two
# for EXACT per-track joins — unlike normalize_track_title(), it preserves accents
# and remix/original markers, so distinct tracks stay distinct.
_FS_INVALID_CHARS = r'<>:"/\|?*'
_FS_INVALID_TO = '_' * len(_FS_INVALID_CHARS)


def canonical_song(name: str) -> str:
    """Map a title to the filename-derived form (S4A-invalid chars -> '_')."""
    if not name:
        return ''
    return ''.join('_' if c in _FS_INVALID_CHARS else c for c in str(name))


def canonical_song_sql(col: str) -> str:
    """SQL expression mirroring canonical_song(). `col` must be a trusted identifier
    (a column name from our own code), never user input."""
    return f"translate({col}, '{_FS_INVALID_CHARS}', '{_FS_INVALID_TO}')"


def _strip_accents(text: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFKD', text)
        if not unicodedata.combining(c)
    )


def normalize_track_title(name: str) -> str:
    """Return a canonical match key for a track title across platforms.

    Lowercases, strips accents, unifies remix markers ("(Remix)", "- Remix" ->
    "remix"), drops "- Original" / "(Original)", and reduces to single-spaced
    alphanumerics. Empty input -> "".
    """
    if not name:
        return ''
    s = _strip_accents(str(name)).lower().strip()
    # Unify remix markers to a trailing " remix"
    s = re.sub(r'[\(\[]\s*remix[^\)\]]*[\)\]]', ' remix', s)
    s = re.sub(r'\s*-\s*remix\b.*', ' remix', s)
    # Drop "original" markers (original == base title)
    s = re.sub(r'[\(\[]\s*original\s*[\)\]]', ' ', s)
    s = re.sub(r'\s*-\s*original\b', ' ', s)
    # Collapse to alphanumerics separated by single spaces
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def track_title_matches(query: str, candidate: str) -> bool:
    """True if `candidate` (a platform title) refers to the same track as `query`
    (the S4A song), tolerant to cross-platform noise.

    Strategy: normalize both, then accept on equality OR containment — which absorbs
    artist prefixes ("1x7xxxxxxx - …") and suffixes ("(free download)") that survive
    normalization. Base vs remix stay DISTINCT: a containment match is only allowed
    when both sides agree on remix status (normalize_track_title appends "remix").
    """
    q = normalize_track_title(query)
    c = normalize_track_title(candidate)
    if not q or not c:
        return False
    if q == c:
        return True
    q_tok, c_tok = q.split(), c.split()
    # Remix is a distinct release: only match base↔base or remix↔remix.
    if ('remix' in q_tok) != ('remix' in c_tok):
        return False
    qb = ' '.join(t for t in q_tok if t != 'remix')
    cb = ' '.join(t for t in c_tok if t != 'remix')
    if not qb or not cb:
        return False
    return qb in cb or cb in qb


def rebuild_release_reference(db, artist_id: int) -> int:
    """Rebuild track_release_reference for one artist from s4a_songs_global.

    Reads the authoritative S4A release dates, normalizes each song name to a
    match_key, keeps the earliest release_date per key (true original release),
    and upserts. Returns the number of reference rows written. Raises on DB error
    (caller decides how to surface it).
    """
    rows = db.fetch_query(
        "SELECT song, MIN(release_date) AS release_date "
        "FROM s4a_songs_global "
        "WHERE artist_id = %s AND release_date IS NOT NULL "
        "GROUP BY song",
        (artist_id,),
    )
    if not rows:
        return 0

    best: dict[str, tuple[str, object]] = {}
    for song, release_date in rows:
        key = normalize_track_title(song)
        if not key:
            continue
        if key not in best or (release_date and best[key][1] and release_date < best[key][1]):
            best[key] = (song, release_date)

    if not best:
        return 0

    now = datetime.now(timezone.utc)
    data = [
        {
            'artist_id': artist_id,
            'match_key': key,
            'title': title,
            'release_date': release_date,
            'source': 's4a_songs_global',
            'updated_at': now,
        }
        for key, (title, release_date) in best.items()
    ]
    db.upsert_many(
        table='track_release_reference',
        data=data,
        conflict_columns=['artist_id', 'match_key'],
        update_columns=['title', 'release_date', 'source', 'updated_at'],
    )
    logger.info("track_release_reference rebuilt for artist %s: %d rows", artist_id, len(data))
    return len(data)


def get_release_dates(db, artist_id: int) -> dict[str, object]:
    """Return {match_key: release_date} for an artist from the reference table."""
    rows = db.fetch_query(
        "SELECT match_key, release_date FROM track_release_reference "
        "WHERE artist_id = %s AND release_date IS NOT NULL",
        (artist_id,),
    )
    return {k: rd for k, rd in rows} if rows else {}
