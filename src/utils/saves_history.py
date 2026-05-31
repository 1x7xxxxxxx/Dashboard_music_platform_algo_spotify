"""
Type: Utility
Daily saves-history snapshotting + long-tail "resurrection" detection.

snapshot_saves: records today's rolling-28d saves count per active song into
s4a_song_saves_daily (the time series s4a_songs_global lacks). Wired into the
daily ml_scoring DAG so history accumulates automatically.

detect_saves_resurrection: flags songs older than ~6 months whose recent saves
momentum spikes above their prior baseline — "spark" candidates worth re-igniting
with a small ad budget. Returns [] until ~2 weeks of history exist (dormant).

Uses: s4a_songs_global (saves source), s4a_song_timeline (age), s4a_song_saves_daily (history)
Persists in: PostgreSQL spotify_etl
"""
from collections import defaultdict
from datetime import date, timedelta

ARTIST_FILTER = "%1x7xxxxxxx%"


def snapshot_saves(db, artist_id: int) -> int:
    """Upsert today's saves snapshot for each of the artist's songs.

    Returns the number of rows written (0 if no saves data yet).
    """
    rows = db.fetch_query(
        """SELECT song, saves FROM s4a_songs_global
           WHERE artist_id = %s AND time_window = '28d'
             AND song NOT ILIKE %s""",
        (artist_id, ARTIST_FILTER),
    )
    if not rows:
        return 0
    today = date.today()
    payload = [
        {"artist_id": artist_id, "song": song, "snapshot_date": today, "saves": int(saves or 0)}
        for song, saves in rows
    ]
    db.upsert_many(
        "s4a_song_saves_daily", payload,
        ["artist_id", "song", "snapshot_date"], ["saves"],
    )
    return len(payload)


def detect_saves_resurrection(db, artist_id: int, *, min_age_days: int = 180,
                              recent_days: int = 7, baseline_days: int = 21,
                              min_spark: int = 50, factor: float = 2.0) -> list[dict]:
    """Return long-tail songs whose recent saves momentum spikes vs their baseline.

    A song qualifies when it is older than min_age_days, has enough saves history,
    and the recent daily saves-gain exceeds both min_spark (over recent_days) and
    `factor`x its prior baseline rate. Dormant ([]) until history accumulates.
    """
    age_rows = db.fetch_query(
        """SELECT song, MIN(date) FROM s4a_song_timeline
           WHERE artist_id = %s AND song NOT ILIKE %s GROUP BY song""",
        (artist_id, ARTIST_FILTER),
    )
    today = date.today()
    age = {song: (today - first).days for song, first in (age_rows or []) if first}

    hist = db.fetch_query(
        """SELECT song, snapshot_date, saves FROM s4a_song_saves_daily
           WHERE artist_id = %s ORDER BY song, snapshot_date""",
        (artist_id,),
    )
    series: dict[str, list[tuple]] = defaultdict(list)
    for song, snap_date, saves in (hist or []):
        series[song].append((snap_date, int(saves or 0)))

    def _value_at(points, days_back):
        """Latest snapshot at or before (latest_date - days_back), else None."""
        target = points[-1][0] - timedelta(days=days_back)
        chosen = None
        for snap_date, saves in points:
            if snap_date <= target:
                chosen = saves
        return chosen

    sparks: list[dict] = []
    for song, points in series.items():
        if age.get(song, 0) < min_age_days or len(points) < 2:
            continue
        latest_saves = points[-1][1]
        s_recent = _value_at(points, recent_days)
        s_base = _value_at(points, recent_days + baseline_days)
        if s_recent is None or s_base is None:
            continue
        recent_gain = latest_saves - s_recent
        baseline_rate = max((s_recent - s_base) / baseline_days, 0.0)
        recent_rate = recent_gain / recent_days
        if recent_gain >= min_spark and recent_rate >= factor * max(baseline_rate, 0.1):
            sparks.append({
                "song": song, "age_days": age.get(song),
                "recent_gain": recent_gain, "baseline_rate": round(baseline_rate, 2),
            })
    sparks.sort(key=lambda s: s["recent_gain"], reverse=True)
    return sparks
