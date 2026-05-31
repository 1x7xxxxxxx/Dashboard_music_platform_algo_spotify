-- 039_tracks_multi_tenant.sql
-- Brick: tracks → multi-tenant (P2 data integrity).
-- Closes the cross-tenant leak documented in .claude/dev-docs/audit-tracks-legacy.md:
-- `tracks.artist_id` is a Spotify-API varchar id (e.g. '7sbfafbLjNZGZJZjZ3xoPB'),
-- NOT the SaaS integer. 4 dashboard readers resolve release dates against `tracks`
-- without any tenant filter, so a 2nd ingested artist would mix tenants.
--
-- Strategy: add a SaaS bridge column on saas_artists + a saas_artist_id FK on tracks,
-- backfill the (currently single) tenant unambiguously, leave the legacy varchar
-- artist_id in place (dropped in a later release cycle once no caller depends on it).
-- Idempotent — safe to re-run.

BEGIN;

-- 1. Bridge column: SaaS artist ↔ Spotify-API artist id.
ALTER TABLE saas_artists
    ADD COLUMN IF NOT EXISTS spotify_artist_id VARCHAR(50);

-- 2. SaaS integer FK on tracks (nullable for now — backfilled below; readers
--    treat NULL as "no tenant match" and fall back gracefully).
ALTER TABLE tracks
    ADD COLUMN IF NOT EXISTS saas_artist_id INTEGER REFERENCES saas_artists(id);

-- 3. Unambiguous auto-bridge: only when there is exactly ONE active SaaS artist
--    with no bridge yet AND exactly ONE distinct legacy artist_id in tracks, link
--    them. No-op (and safe) the moment a 2nd tenant exists — multi-tenant bridges
--    must then be set explicitly (config / admin), never guessed.
DO $$
DECLARE
    v_saas_id   INTEGER;
    v_spotify   VARCHAR(50);
    n_saas      INTEGER;
    n_spotify   INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_saas
        FROM saas_artists WHERE active = TRUE AND spotify_artist_id IS NULL;
    SELECT COUNT(DISTINCT artist_id) INTO n_spotify
        FROM tracks WHERE artist_id IS NOT NULL;

    IF n_saas = 1 AND n_spotify = 1 THEN
        SELECT id INTO v_saas_id
            FROM saas_artists WHERE active = TRUE AND spotify_artist_id IS NULL;
        SELECT DISTINCT artist_id INTO v_spotify
            FROM tracks WHERE artist_id IS NOT NULL;

        UPDATE saas_artists SET spotify_artist_id = v_spotify WHERE id = v_saas_id;
        RAISE NOTICE 'Auto-bridge: saas_artists.id=% ← spotify_artist_id=%',
            v_saas_id, v_spotify;
    ELSE
        RAISE NOTICE 'Auto-bridge skipped (active-unbridged saas=%, distinct spotify=%) — set spotify_artist_id manually.',
            n_saas, n_spotify;
    END IF;
END $$;

-- 4. Backfill tracks.saas_artist_id from the bridge.
UPDATE tracks t
    SET saas_artist_id = sa.id
    FROM saas_artists sa
    WHERE sa.spotify_artist_id = t.artist_id
      AND t.saas_artist_id IS NULL;

-- 5. Index for the new tenant filter.
CREATE INDEX IF NOT EXISTS idx_tracks_saas_artist ON tracks (saas_artist_id);

COMMIT;
