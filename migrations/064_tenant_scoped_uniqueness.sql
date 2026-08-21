-- 064 — A row belongs to one tenant, and cannot be handed to another.
--
-- Two beta artists saw the admin's data. One reason was upstream (identity
-- falling back to the admin's env vars, fixed in code); the other is here, in
-- the schema: `youtube_videos` and `youtube_channels` were UNIQUE on the
-- PLATFORM id alone, while the collector upserted with `artist_id` among the
-- updated columns. Two tenants touching the same video therefore did not get a
-- row each — the second collection RE-ASSIGNED the existing row, and the first
-- tenant's data silently vanished from their (artist-scoped) views.
--
-- Uniqueness is per (tenant, platform object). Two tenants may legitimately
-- share a video — a feature, a collab, or simply the same channel entered twice
-- — and each must keep their own row.
--
-- Meta (`meta_campaigns`/`meta_adsets`/`meta_ads`) keeps its platform-id primary
-- keys on purpose: 15 foreign keys reference them, and converting those is a
-- migration of a different size. Ownership transfer there is instead removed in
-- code (artist_id dropped from every upsert's update_columns), so a shared ad
-- account can no longer steal a row — it simply will not create a second one.
-- Tracked as a follow-up, not silently skipped.
--
-- Idempotent: safe to re-run (make migrate replays every file).

BEGIN;

-- ── youtube_videos ──────────────────────────────────────────────────────────
ALTER TABLE youtube_videos DROP CONSTRAINT IF EXISTS unique_video_id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_youtube_videos_artist_video
    ON youtube_videos (artist_id, video_id);

-- ── youtube_channels ────────────────────────────────────────────────────────
ALTER TABLE youtube_channels DROP CONSTRAINT IF EXISTS unique_channel_id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_youtube_channels_artist_channel
    ON youtube_channels (artist_id, channel_id);

-- ── The canary tenant flag (used by `make artist-preflight`) ────────────────
-- A permanent non-billable tenant whose only job is to prove, before we invite a
-- real artist, that a NON-admin account can connect, collect and read its own
-- data. Excluded from billing, alerting and stats by this flag.
ALTER TABLE saas_artists ADD COLUMN IF NOT EXISTS is_canary BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;
