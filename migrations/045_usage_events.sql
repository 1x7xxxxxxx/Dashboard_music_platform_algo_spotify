-- 045_usage_events.sql — first-party product-usage event log (Option A).
-- Server-side telemetry: page views + key actions. No third-party egress.
-- Idempotent.

CREATE TABLE IF NOT EXISTS usage_events (
    id          BIGSERIAL PRIMARY KEY,
    artist_id   INTEGER,
    role        TEXT,
    session_id  TEXT,
    event       TEXT NOT NULL,
    page        TEXT,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    meta        JSONB
);

CREATE INDEX IF NOT EXISTS idx_usage_events_ts          ON usage_events (ts);
CREATE INDEX IF NOT EXISTS idx_usage_events_artist_ts   ON usage_events (artist_id, ts);
CREATE INDEX IF NOT EXISTS idx_usage_events_event       ON usage_events (event);
