-- Migration 049 — Cross-platform track link + Meta suggestion provenance (B1)
-- Run: make migrate   (or, from PowerShell, see CLAUDE.md § Running Migrations)
--
-- track_platform_link: one row per (canonical track) × platform, recording which
-- platform-local free-text title is bound to that canonical track. The canonical
-- entity is track_release_reference(artist_id, match_key) — referenced by
-- (artist_id, match_key), NOT a surrogate id, because rebuild_release_reference()
-- upserts on match_key (the stable join key; id is not guaranteed stable).
-- 'rejected' rows are tombstones so the suggester stops re-proposing a pair.
-- platform_ref_id holds a stable id where the platform has one (soundcloud
-- track_id, youtube video_id, imusician isrc); NULL for name-only platforms.

CREATE TABLE IF NOT EXISTS track_platform_link (
    id              SERIAL       PRIMARY KEY,
    artist_id       INTEGER      NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    match_key       VARCHAR(255) NOT NULL,
    platform        VARCHAR(32)  NOT NULL,
    platform_title  VARCHAR(512) NOT NULL,
    platform_ref_id VARCHAR(255),
    status          VARCHAR(16)  NOT NULL DEFAULT 'confirmed',
    confidence      REAL,
    method          VARCHAR(32),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (artist_id, platform, platform_title, match_key)
);

CREATE INDEX IF NOT EXISTS idx_tpl_artist_key
    ON track_platform_link (artist_id, match_key);
CREATE INDEX IF NOT EXISTS idx_tpl_artist_platform
    ON track_platform_link (artist_id, platform, status);

COMMENT ON TABLE track_platform_link IS
    'Confirmed/rejected links between a canonical track (track_release_reference.match_key) '
    'and a platform-local title. Powers the cross-platform mapping view (B1).';

-- Meta campaign mapping: suggestion provenance (nullable → backward compatible).
ALTER TABLE campaign_track_mapping ADD COLUMN IF NOT EXISTS confidence REAL;
ALTER TABLE campaign_track_mapping ADD COLUMN IF NOT EXISTS method VARCHAR(32);
ALTER TABLE campaign_track_mapping
    ADD COLUMN IF NOT EXISTS auto_suggested BOOLEAN NOT NULL DEFAULT FALSE;
