# Audit — `tracks` legacy table (multi-tenant non-conformance)

> **RESOLVED 2026-05-31** — `migrations/039_tracks_multi_tenant.sql` implemented the
> recommended path below (bridge column + `saas_artist_id` FK + backfill; 4 readers and
> the writer updated). The legacy varchar `tracks.artist_id` is kept for now and will be
> dropped in a later release cycle once no caller depends on it. This doc is retained as
> the design rationale.

Generated 2026-05-14 after `meta_mapping.py` crashed with `operator does not exist: character varying = integer`.

## Schema

```
                                 Table "public.tracks"
    Column    |            Type             | Nullable |      Default
--------------+-----------------------------+----------+-------------------
 track_id     | character varying(50)       | not null |
 track_name   | character varying(255)      | not null |
 artist_id    | character varying(50)       |          |
 popularity   | integer                     |          | 0
 duration_ms  | integer                     |          |
 explicit     | boolean                     |          | false
 album_name   | character varying(255)      |          |
 release_date | date                        |          |
 collected_at | timestamp                   |          | CURRENT_TIMESTAMP
Indexes:
    "tracks_pkey" PRIMARY KEY, btree (track_id)
    "idx_tracks_artist" btree (artist_id)
Foreign-key constraints:
    "tracks_artist_id_fkey" FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
```

Population on 2026-05-14: **11 rows, 1 distinct `artist_id`** (legacy single-tenant import).

`artist_id` is a Spotify-API artist identifier (e.g. `"6XyY86QOPPRYVxw3FmFnNn"`), **NOT** the SaaS `saas_artists.id` integer. There is no bridge column — `saas_artists` has no `spotify_artist_id` column.

## Caller inventory

| Caller | Line | Op | Passes `artist_id` as | Filters by artist_id? | Crash risk | Multi-tenant leak risk |
|---|---|---|---|---|---|---|
| `airflow/dags/spotify_api_daily.py` | 201 | UPSERT (writer) | Spotify varchar (from collector) | n/a (write) | None | — |
| `src/dashboard/views/meta_x_spotify.py` | 22 | SELECT | — | **No filter** | None | **YES** — returns all tenants' tracks |
| `src/dashboard/views/spotify_s4a_combined.py` | 140 | SELECT MAX(release_date) | — | **No filter** | None | **YES** — global MAX across tenants |
| `src/dashboard/views/spotify_s4a_combined.py` | 246 | SELECT release_date by track_name | — | **No filter** (lookup by name) | None | **YES** — name collision across tenants |
| `src/dashboard/views/trigger_algo.py` | 1118 | SELECT release_date by track_name | — | **No filter** (lookup by name) | None | **YES** — name collision across tenants |
| `src/dashboard/views/meta_mapping.py` | (was 22) | SELECT track_name | SaaS integer (int) | yes (broken) | **WAS crash, fixed today** by repointing to `s4a_song_timeline.song` | — |

Today's crash was a side-effect: `meta_mapping.py` was the only caller that did attempt a multi-tenant filter, which exposed the type incompatibility. The other 4 readers don't filter at all — they "work" only because the table currently holds a single artist's data.

## Risk classification

- **P2 (data integrity)** — as soon as a second artist gets ingested via `spotify_api_daily`, the 4 readers will mix tenants. `meta_x_spotify` returns track names from other artists; `spotify_s4a_combined` and `trigger_algo` resolve release-date lookups by `track_name` only, returning the wrong tenant's release date if titles collide.
- **P1 (crash)** — only on callers that pass an integer `artist_id` (fixed: `meta_mapping`). No remaining P1 risk because the other readers don't pass one at all.

## Recommended migration path (future P2 brick)

Single migration `migrations/0XX_tracks_multi_tenant.sql`:

1. Add `saas_artists.spotify_artist_id VARCHAR(50)` column. Backfill from `artist_credentials.creds_json->>'spotify_artist_id'` if present, NULL otherwise.
2. Add `tracks.saas_artist_id INTEGER REFERENCES saas_artists(id)`. Backfill via `UPDATE tracks t SET saas_artist_id = sa.id FROM saas_artists sa WHERE sa.spotify_artist_id = t.artist_id`. NOT NULL once backfilled.
3. Add `UNIQUE (saas_artist_id, track_id)` if same `track_id` could legitimately appear under multiple SaaS artists (shared catalog).
4. Update the 4 readers to add `WHERE saas_artist_id = %s` (current SaaS integer).
5. Update the writer (`spotify_api_daily`) to look up `saas_artist_id` from `saas_artists` before inserting, falling back to the existing varchar `artist_id`.
6. Keep `tracks.artist_id` (varchar) for now — drop in a follow-up after a release cycle confirms no caller still uses it.

**Do NOT** drop `tracks` — it's actively written by `spotify_api_daily` and read by 4 views.

## Short-term mitigation (already done)

- `src/dashboard/views/meta_mapping.py:22` — repointed `_load_tracks` to `s4a_song_timeline.song` with mandatory `NOT ILIKE '%1x7xxxxxxx%'` filter. Multi-tenant-correct because `s4a_song_timeline.artist_id` is the SaaS integer.

## When to re-audit

- After any new caller is added to `tracks` (`grep -rn "FROM tracks" src/ airflow/`).
- Before `spotify_api_daily` is unpaused for a second artist.
- When implementing the migration above.
