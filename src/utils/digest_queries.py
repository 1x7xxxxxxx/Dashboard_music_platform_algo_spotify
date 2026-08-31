"""SQL used by the weekly KPI digest, kept outside the DAG so it can be tested.

Type: Utility
Uses: nothing (pure string constants)
Depends on: the `soundcloud_tracks_daily` schema
Persists in: nothing

Why this module exists rather than a literal inside `airflow/dags/weekly_digest.py`:
a DAG module imports `airflow`, which is absent from several interpreters this
suite runs under, so a guard living next to the DAG skips in silence — exactly the
way the defect below survived. A pure module imports everywhere.

---
rex:
  - date: 2026-08-31
    issue: "weekly_digest keyed a SoundCloud snapshot on `collected_at = MAX(collected_at)`, but the collector stamps every row of one batch with its own microsecond; the match hit a single track and mailed the artist a -21,324 plays collapse that never happened (2,229 reported against a real 23,557)"
    fix: "Key the snapshot on `collected_at::date` — the grain the table's own UNIQUE constraint declares — with DISTINCT ON per track, and drop the COALESCE so an absent snapshot reads N/A instead of a fabricated 0"
    severity: crit
---
"""
from __future__ import annotations

# A snapshot is identified by its DAY, never by `collected_at` itself.
#
# `soundcloud_tracks_daily` declares that grain in its own constraint:
#     UNIQUE (artist_id, track_id, (collected_at::date))
# while `collected_at` carries a per-row microsecond — measured in production on
# 2026-08-31, one batch of 19 tracks held 19 distinct timestamps
# (11:00:04.101372, .101370, .101367 …). Equality against MAX(collected_at)
# therefore selects the LAST ROW INSERTED, not the batch.
#
# DISTINCT ON keeps the sum correct even if a day ever receives two runs, and the
# absence of COALESCE is deliberate: no snapshot must render "N/A", never a 0 that
# reads as a real measurement.
SOUNDCLOUD_WEEKLY_DELTA_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (track_id) playback_count
    FROM soundcloud_tracks_daily
    WHERE artist_id = %s
      AND collected_at::date = (
          SELECT MAX(collected_at::date) FROM soundcloud_tracks_daily
          WHERE artist_id = %s
      )
    ORDER BY track_id, collected_at DESC
),
week_ago AS (
    SELECT DISTINCT ON (track_id) playback_count
    FROM soundcloud_tracks_daily
    WHERE artist_id = %s
      AND collected_at::date = (
          SELECT MAX(collected_at::date) FROM soundcloud_tracks_daily
          WHERE artist_id = %s AND collected_at::date <= CURRENT_DATE - 7
      )
    ORDER BY track_id, collected_at DESC
)
SELECT (SELECT SUM(playback_count) FROM latest)   AS latest_total,
       (SELECT SUM(playback_count) FROM week_ago) AS week_ago_total
"""
