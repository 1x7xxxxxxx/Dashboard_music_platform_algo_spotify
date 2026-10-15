"""Where a "last N days" window over S4A ends: the last imported day, not today (R571).

Type: Utility
Uses: v_s4a_song_daily (gold view over the hand-imported S4A CSVs)
Triggers: ml_inference.build_features, api kpis, PDF collectors, period_side_metrics
Persists in: nothing

Owner, 2026-10-15: a track showed its playlist adds and « 0 écoute sur 7 j ». S4A is a
CSV the artist drops by hand; `day >= CURRENT_DATE - 7` reads an empty window as soon
as the last import is a week old, and `COALESCE(SUM, 0)` turns that absence into a
zero. Every such window ends on the tenant's last imported day instead — the ARTIST's,
never the song's: a song silent while the others kept streaming is a real zero.
"""
from __future__ import annotations


def s4a_last_day(artist_id: int | None) -> tuple[str, tuple]:
    """SQL scalar sub-select of the last imported S4A day, and its parameters.

    `artist_id` None = every tenant (admin PDF): the newest import of any of them.
    """
    if artist_id is None:
        return "(SELECT MAX(day) FROM v_s4a_song_daily)", ()
    return "(SELECT MAX(day) FROM v_s4a_song_daily WHERE artist_id = %s)", (artist_id,)


def s4a_last_day_value(db, artist_id: int | None):
    """The last imported S4A day as a date (None when nothing was ever imported)."""
    sql, params = s4a_last_day(artist_id)
    rows = db.fetch_query(f"SELECT {sql}", params or None)
    return rows[0][0] if rows else None
