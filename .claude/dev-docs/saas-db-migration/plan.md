# Plan — SaaS DB Migration (Brick 1)

## Objective
Add multi-tenant support by introducing a `saas_artists` table and an `artist_credentials` table, then adding `artist_id` FK to all existing data tables and migrating current single-artist data to `artist_id = 1`.

---

## Affected Files

| File | Role | Change |
|---|---|---|
| `init_db.sql` | Initial schema | ADD new tables + ALTER TABLE statements |
| `scripts/migrate_saas_artist_id.py` | One-shot migration script | NEW — assigns artist_id=1 to all existing rows |
| `src/database/saas_schema.py` | Schema definitions for new tables | NEW |
| `src/database/postgres_handler.py` | DB utility | Maybe add `execute_ddl()` if needed |
| `src/database/s4a_schema.py` | S4A tables | Modify UNIQUE constraints to include artist_id |
| `src/database/apple_music_csv_schema.py` | Apple Music tables | Modify UNIQUE constraints |
| `src/database/youtube_schema.py` | YouTube tables | Add artist_id FK |
| `src/database/meta_ads_schema.py` | Meta Ads tables | Add artist_id FK |
| `src/database/hypeddit_schema.py` | Hypeddit tables | Add artist_id FK + update UNIQUE |
| `src/dashboard/app.py` | Streamlit entry point | Replace ARTIST_NAME_FILTER with session artist_id (deferred to Brick 2) |

> SoundCloud and Instagram schemas: check `src/database/` (no dedicated schema file found yet — likely inline in collectors).

---

## Implementation Steps

### Step 1 — Create `saas_artists` table
**Why `saas_artists` and not `artists`**: the `artists` table already exists for Spotify track metadata (stores Spotify artist_id as VARCHAR PK). Reusing it would break the Spotify data model. Use a separate tenant table.

```sql
CREATE TABLE IF NOT EXISTS saas_artists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    tier VARCHAR(20) NOT NULL DEFAULT 'basic'  -- 'basic' | 'premium'
        CHECK (tier IN ('basic', 'premium')),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed row for current single artist
INSERT INTO saas_artists (id, name, slug, tier, active)
VALUES (1, 'Artist Default', 'default', 'premium', true)
ON CONFLICT (id) DO NOTHING;
```

### Step 2 — Create `artist_credentials` table

```sql
CREATE TABLE IF NOT EXISTS artist_credentials (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,  -- 'spotify', 'youtube', 'meta', 'soundcloud', 'instagram'
    token_encrypted TEXT,           -- Fernet-encrypted token
    extra_config JSONB,             -- client_id, account_id, etc.
    expires_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, platform)
);
```

### Step 3 — Add `artist_id` to all data tables (ALTER TABLE)
For each table below, add `artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id)` and update UNIQUE constraints.

**CRITICAL**: UNIQUE constraints that don't include `artist_id` must be dropped and recreated to avoid collisions between artists.

| Table | Old UNIQUE | New UNIQUE |
|---|---|---|
| `s4a_songs_global` | `(song)` | `(artist_id, song)` |
| `s4a_song_timeline` | `(song, date)` | `(artist_id, song, date)` |
| `s4a_audience` | `(date)` | `(artist_id, date)` |
| `apple_songs_performance` | `(song_name)` | `(artist_id, song_name)` |
| `apple_daily_plays` | `(song_name, date)` | `(artist_id, song_name, date)` |
| `apple_listeners` | `(date)` | `(artist_id, date)` |
| `meta_campaigns` | PK = campaign_id | Add artist_id column (no UNIQUE change needed) |
| `meta_adsets` | PK = adset_id | Add artist_id column |
| `meta_ads` | PK = ad_id | Add artist_id column |
| `meta_insights` | `(ad_id, date)` | no change (ad_id already unique per artist) |
| `hypeddit_campaigns` | `(campaign_name)` | `(artist_id, campaign_name)` |
| `hypeddit_daily_stats` | `(campaign_name, date)` | `(artist_id, campaign_name, date)` |
| `youtube_channels` | `(channel_id)` | no change (channel_id is globally unique) |
| `youtube_videos` | `(video_id)` | no change |
| `youtube_playlists` | `(playlist_id)` | no change |
| `youtube_comments` | `(comment_id)` | no change |
| `track_popularity_history` | `(track_id, date)` | `(artist_id, track_id, date)` |

### Step 4 — Write migration script
`scripts/migrate_saas_artist_id.py`: connects to DB, sets `artist_id = 1` on all existing rows (if DEFAULT 1 is used in ALTER TABLE, existing rows are already migrated at DDL time).

### Step 5 — Update schema Python files
Update `S4A_SCHEMA`, `APPLE_MUSIC_CSV_SCHEMA`, `META_ADS_SCHEMA`, `HYPEDDIT_SCHEMA`, `YOUTUBE_SCHEMA` CREATE TABLE SQL to include `artist_id` and new UNIQUE constraints for any future `CREATE IF NOT EXISTS` runs.

### Step 6 — Create `src/database/saas_schema.py`
Contains `SAAS_SCHEMA` dict with SQL for `saas_artists` and `artist_credentials`. Follow the pattern of `s4a_schema.py`.

### Step 7 — Update `init_db.sql`
Append the new `saas_artists` + `artist_credentials` table definitions so fresh installs (Railway, new Docker) get the full schema.

---

## Risks / Watch-outs

- **`ARTIST_NAME_FILTER`**: The constant `ARTIST_NAME_FILTER = "1x7xxxxxxx"` in `app.py` filters the "Total" row from S4A CSVs. This must remain until Brick 2 (Auth) injects `artist_id` into session state. Do NOT remove it in this brick.
- **`artists` table name collision**: The existing `artists` table is for Spotify track metadata (PK = Spotify artist_id VARCHAR). Do NOT rename or repurpose it. Use `saas_artists` for the new tenant table.
- **`hypeddit_schema.py` DROP TABLE**: The current `hypeddit_campaigns` SQL includes `DROP TABLE IF EXISTS ... CASCADE` — dangerous in production. Do not run that block on an existing DB.
- **`autocommit=True`** in PostgresHandler: DDL (ALTER TABLE, DROP CONSTRAINT) runs fine, but be aware there's no transaction rollback on error in migration scripts.
- **`meta_campaigns` FK chain**: `meta_adsets` → `meta_campaigns`, `meta_ads` → `meta_adsets` + `meta_campaigns`, `meta_insights` → `meta_ads`. Adding `artist_id` must not break FK chain.
- **SoundCloud/Instagram**: No dedicated schema files found — check inline table creation in collectors before altering.
- **Railway deploy**: `init_db.sql` runs once at container start. For an already-provisioned DB, the migration script must be run manually once.

---

## Out of Scope (this brick only)

- Authentication / login page (Brick 2)
- Admin interface (Brick 3)
- Credential form UI (Brick 4)
- CSV upload via Streamlit (Brick 5)
- Parameterized DAGs (Brick 6)
- Fernet encryption of credentials (deferred to Brick 4)
- Railway deployment setup
- Any changes to Airflow DAGs
