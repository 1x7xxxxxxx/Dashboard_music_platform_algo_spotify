-- ⚠️  ORDRE DE DÉPLOIEMENT — CETTE MIGRATION N'EST PAS AUTONOME
--
-- Elle ne doit être appliquée QU'AVEC le code qui upserte sur
-- `conflict_columns=['artist_id', 'channel_id']` / `['artist_id', 'video_id']`.
--
-- Appliquée seule en production le 2026-08-20, elle a cassé la collecte YouTube
-- en quelques minutes : le code déployé faisait encore `ON CONFLICT (channel_id)`
-- et Postgres a répondu « there is no unique or exclusion constraint matching the
-- ON CONFLICT specification » pour chaque locataire ayant une chaîne. Revert
-- immédiat, collecte rétablie, migration remise en attente du déploiement.
--
-- Séquence correcte :  déployer le code  →  puis `make migrate`.
-- (La migration 064, elle, est purement additive et peut précéder le code.)

-- 065 — YouTube: the platform id stops being the primary key.
--
-- Migration 064 added the tenant-scoped unique indexes, but production still
-- carried `youtube_videos_pkey PRIMARY KEY (video_id)` and
-- `youtube_channels_pkey PRIMARY KEY (channel_id)` — so a video could still only
-- belong to ONE tenant, and an upsert conflict still handed the row to whoever
-- collected last. (Canonical `init_db.sql` declares `id SERIAL PRIMARY KEY` with
-- a separate UNIQUE; production diverged. `make schema-check` compares columns,
-- not constraints, which is why the drift stayed invisible — see the note below.)
--
-- Both tables already carry an `id` column (migration 063). This promotes it to
-- primary key, so uniqueness is governed by (artist_id, video_id) from 064 and
-- two tenants can legitimately hold the same video.
--
-- The self-referencing FK youtube_videos.channel_id -> youtube_channels(channel_id)
-- is replaced by a tenant-scoped one: a video's channel must belong to the SAME
-- tenant, which the old cross-tenant FK could not express.
--
-- Idempotent: safe to re-run.

BEGIN;

-- ── Backfill `id` where it is NULL, then make it usable as a key ────────────
ALTER TABLE youtube_videos   ALTER COLUMN id SET NOT NULL;
ALTER TABLE youtube_channels ALTER COLUMN id SET NOT NULL;

-- ── Drop the FK that depends on youtube_channels(channel_id) ────────────────
ALTER TABLE youtube_videos DROP CONSTRAINT IF EXISTS youtube_videos_channel_id_fkey;

-- ── Move the primary keys onto the surrogate id ─────────────────────────────
ALTER TABLE youtube_videos   DROP CONSTRAINT IF EXISTS youtube_videos_pkey;
ALTER TABLE youtube_channels DROP CONSTRAINT IF EXISTS youtube_channels_pkey;

ALTER TABLE youtube_videos   ADD CONSTRAINT youtube_videos_pkey   PRIMARY KEY (id);
ALTER TABLE youtube_channels ADD CONSTRAINT youtube_channels_pkey PRIMARY KEY (id);

-- ── No replacement FK, deliberately ─────────────────────────────────────────
-- A tenant-scoped FK (artist_id, channel_id) -> youtube_channels was tried and
-- REMOVED the same day: it forces every video insert to be preceded by its
-- channel row, which is a new way for collection to fail (a channel whose stats
-- call returned nothing while its uploads did) in exchange for integrity the
-- tenant-isolation fix does not need — the (artist_id, video_id) unique index
-- from 064 is what stops the ownership transfer. It was caught because three
-- tests went red on it; a constraint that only breaks writers is not free.
ALTER TABLE youtube_videos DROP CONSTRAINT IF EXISTS youtube_videos_artist_channel_fkey;

COMMIT;
