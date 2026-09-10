"""SQL and formatters used by the weekly KPI digest, kept outside the DAG so they
can be tested.

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


# ── Spotify for Artists : les streams de la semaine ─────────────────────────
#
# PAS de COALESCE, pour la raison écrite plus haut à propos de SoundCloud : un
# locataire qui n'a jamais déposé de CSV S4A n'a pas « 0 stream cette semaine », il
# n'a pas de mesure. `SUM(CASE …)` rend NULL sur zéro ligne, et c'est la bonne
# réponse. Mesuré le 2026-09-10 : ce fichier appliquait déjà la règle à SoundCloud,
# à Instagram et au ML, et la contredisait ici et sur Meta.
#
# `DISTINCT ON (date, song)` garde le dernier dépôt pour un jour donné : deux
# imports du même jour ne doivent pas doubler les streams.
SPOTIFY_WEEKLY_STREAMS_SQL = """
SELECT
    SUM(CASE WHEN date >= CURRENT_DATE - 7 THEN streams END) AS last_7d,
    SUM(CASE WHEN date >= CURRENT_DATE - 14 AND date < CURRENT_DATE - 7 THEN streams END) AS prev_7d
FROM (
    SELECT DISTINCT ON (date, song) date, streams
    FROM s4a_song_timeline
    WHERE artist_id = %s
      AND song NOT ILIKE '%%1x7xxxxxxx%%'
      AND date >= CURRENT_DATE - 14
    ORDER BY date, song, collected_at DESC
) sub
"""

# ── Meta Ads : dépense et CTR de la semaine ─────────────────────────────────
#
# `ELSE NULL` et non `ELSE 0` : sans impression, le taux de clic n'est pas nul, il
# est indéfini — 0/0. Annoncer « 0,00 % » à un artiste qui n'a jamais fait de
# publicité lui décrit une campagne qui n'existe pas.
META_WEEKLY_SPEND_SQL = """
SELECT
    SUM(spend),
    CASE WHEN SUM(impressions) > 0
         THEN ROUND((SUM(link_clicks)::numeric / SUM(impressions)::numeric) * 100, 2)
         ELSE NULL END
FROM meta_insights_performance
WHERE artist_id = %s
  AND date_start >= CURRENT_DATE - 7
"""


def fmt_value(val, spec: str = ",", suffix: str = "") -> str:
    """Une quantité, ou « N/A » — jamais un zéro fabriqué.

    Il existe parce que les gabarits du digest formatent avec `:,` / `:.2f`, qui
    LÈVENT sur `None`. Sans lui, « ne pas inventer de zéro » se paierait d'un e-mail
    non envoyé : le correctif honnête deviendrait une panne.
    """
    if val is None:
        return "<span style='color:#888'>N/A</span>"
    return f"{val:{spec}}{suffix}"


def fmt_delta(val, suffix: str = "") -> str:
    """Un écart signé et coloré, ou « N/A ». Jumeau de `fmt_value` pour les variations."""
    if val is None:
        return "<span style='color:#888'>N/A</span>"
    color = "#27ae60" if val >= 0 else "#e74c3c"
    sign = "+" if val >= 0 else ""
    return f"<span style='color:{color}'>{sign}{val:,}{suffix}</span>"
