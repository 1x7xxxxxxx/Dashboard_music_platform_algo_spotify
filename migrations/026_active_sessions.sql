-- Migration 026: active_sessions table (Brick 32 — Live Activity widget)
-- One row per artist; last_heartbeat refreshed by the dashboard on user activity.
-- Counted as "live" while last_heartbeat > NOW() - INTERVAL '5 minutes'.
-- Identity stays in saas_artists; activity state lives here to keep them decoupled.

CREATE TABLE IF NOT EXISTS active_sessions (
    artist_id      INTEGER     PRIMARY KEY REFERENCES saas_artists(id) ON DELETE CASCADE,
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_active_sessions_heartbeat
    ON active_sessions (last_heartbeat DESC);
