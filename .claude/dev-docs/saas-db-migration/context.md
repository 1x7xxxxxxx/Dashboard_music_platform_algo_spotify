# Context — SaaS DB Migration

## Key Architectural Decisions
- **Multi-tenancy**: shared schema with `artist_id` FK on all tables (NOT per-schema isolation)
- **Tenant table**: `saas_artists` (NOT `artists` — that table is already used for Spotify metadata)
- **Credentials table**: `artist_credentials` (Fernet-encrypted tokens, one row per artist+platform)
- **Auth frontend**: `streamlit-authenticator` (Brick 2, not this brick)
- **Hosting**: Railway (Docker-native, managed Postgres)
- **No FastAPI**: Streamlit stays as the only frontend

## Database: Full Table Inventory

### Existing tables (in `init_db.sql` / schema files)

**Spotify API** (`init_db.sql`):
- `artists(artist_id VARCHAR PK, name, followers, popularity, genres, collected_at)` — Spotify artist metadata, NOT the tenant table
- `tracks(track_id VARCHAR PK, artist_id FK→artists, ...)` — Spotify tracks
- `track_popularity_history(id SERIAL PK, track_id, track_name, popularity, date, UNIQUE(track_id, date))`
- `artist_history(id SERIAL PK, artist_id FK→artists, followers, popularity, collected_at)`

**Spotify for Artists** (`src/database/s4a_schema.py`):
- `s4a_songs_global(id SERIAL PK, song, listeners, streams, saves, release_date, UNIQUE(song))`
- `s4a_song_timeline(id SERIAL PK, song, date, streams, UNIQUE(song, date))`
- `s4a_audience(id SERIAL PK, date, listeners, streams, followers, UNIQUE(date))`

**Apple Music** (`src/database/apple_music_csv_schema.py`):
- `apple_songs_performance(id SERIAL PK, song_name, album_name, plays, listeners, UNIQUE(song_name))`
- `apple_daily_plays(id SERIAL PK, song_name, date, plays, UNIQUE(song_name, date))`
- `apple_listeners(id SERIAL PK, date, listeners, UNIQUE(date))`

**YouTube** (`src/database/youtube_schema.py`):
- `youtube_channels(id SERIAL PK, channel_id UNIQUE, channel_name, subscriber_count, video_count, view_count, ...)`
- `youtube_channel_history(id SERIAL PK, channel_id, subscriber_count, video_count, view_count, collected_at)`
- `youtube_videos(id SERIAL PK, video_id UNIQUE, channel_id, title, published_at, ...)`
- `youtube_video_stats(id SERIAL PK, video_id, view_count, like_count, comment_count, collected_at)`
- `youtube_playlists(id SERIAL PK, playlist_id UNIQUE, channel_id, title, video_count, ...)`
- `youtube_comments(id SERIAL PK, comment_id UNIQUE, video_id, author, text, published_at, ...)`

**Meta Ads** (`src/database/meta_ads_schema.py`):
- `meta_campaigns(campaign_id VARCHAR PK, campaign_name, status, objective, daily_budget, ...)`
- `meta_adsets(adset_id VARCHAR PK, adset_name, campaign_id FK, status, targeting JSONB, ...)`
- `meta_ads(ad_id VARCHAR PK, ad_name, adset_id FK, campaign_id FK, status, ...)`
- `meta_insights(id SERIAL PK, ad_id FK, date, impressions, clicks, spend, reach, cpc, cpm, ctr, UNIQUE(ad_id, date))`

**Hypeddit** (`src/database/hypeddit_schema.py`):
- `hypeddit_campaigns(id SERIAL PK, campaign_name UNIQUE, is_active, created_at)`
- `hypeddit_daily_stats(id SERIAL PK, campaign_name FK, date, visits, clicks, budget, ctr, cost_per_click, UNIQUE(campaign_name, date))`
- WARNING: the schema SQL contains `DROP TABLE IF EXISTS ... CASCADE` — do NOT re-run on live DB

**SoundCloud / Instagram**: no dedicated schema file in `src/database/`. Tables likely created inline in collectors. Must verify before adding `artist_id`.

### New tables to create (this brick)
- `saas_artists(id SERIAL PK, name, slug UNIQUE, tier CHECK IN ('basic','premium'), active, created_at)`
- `artist_credentials(id SERIAL PK, artist_id FK→saas_artists, platform, token_encrypted, extra_config JSONB, expires_at, UNIQUE(artist_id, platform))`

## Files Read This Session
- `init_db.sql` — base schema (Spotify tables + DB creation)
- `src/database/s4a_schema.py` — S4A tables
- `src/database/apple_music_csv_schema.py` — Apple Music tables
- `src/database/youtube_schema.py` — YouTube tables
- `src/database/meta_ads_schema.py` — Meta Ads tables
- `src/database/hypeddit_schema.py` — Hypeddit tables
- `src/database/postgres_handler.py` — DB utility (autocommit=True, fetch_df, fetch_query, upsert_many)

## Reference Implementation Pattern
- Schema defined as dict `{table_name: CREATE SQL}` in `src/database/<platform>_schema.py`
- `get_create_table_sql(name)` + `get_all_tables()` helper functions
- `PostgresHandler.execute_query(sql)` to run DDL
- Table creation verified with `db.table_exists()` + `db.get_table_count()`

## Current State
| What | Status |
|---|---|
| `saas_artists` table | Does NOT exist |
| `artist_credentials` table | Does NOT exist |
| `artist_id` FK on data tables | Does NOT exist |
| Existing data | Single artist, needs `artist_id = 1` assigned |
| SoundCloud/Instagram schemas | Unknown — check collectors |

## Key Constant to Preserve (until Brick 2)
```python
# src/dashboard/app.py
ARTIST_NAME_FILTER = "1x7xxxxxxx"  # Filters "Total" row from S4A CSVs
```
Do NOT remove this in Brick 1. It will be replaced in Brick 2 when session-based `artist_id` is introduced.

## Open Questions
1. Do SoundCloud and Instagram have dedicated schema files, or are tables created inline in collectors?
2. Does `track_popularity_history` need `artist_id`? (It stores `track_id` but `track_id` is scoped to a Spotify artist — so yes, needed for proper multi-tenant isolation.)
3. Should we use `INTEGER DEFAULT 1` on ALTER TABLE to auto-migrate existing data, or run an explicit UPDATE?

## Resume Instructions
Read this file, then open `.claude/dev-docs/saas-db-migration/checklist.md` to see progress and pick up where it left off.
Start with Step 1: creating `src/database/saas_schema.py` and updating `init_db.sql`.
