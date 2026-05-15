-- 027 — Instagram media catalogue + per-post insights
-- Idempotent. Account-level stats remain in instagram_daily_stats.
-- UNIQUE includes artist_id (multi-tenant); matches upsert conflict_columns.

CREATE TABLE IF NOT EXISTS instagram_media (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    media_id VARCHAR(255) NOT NULL,
    caption TEXT,
    media_type VARCHAR(30),
    permalink TEXT,
    media_url TEXT,
    timestamp TIMESTAMP,
    like_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_instagram_media UNIQUE (artist_id, media_id)
);

CREATE TABLE IF NOT EXISTS instagram_media_insights (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    media_id VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    engagement INTEGER DEFAULT 0,
    saved INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_instagram_media_insights UNIQUE (artist_id, media_id, date)
);

CREATE INDEX IF NOT EXISTS idx_instagram_media_artist ON instagram_media(artist_id);
CREATE INDEX IF NOT EXISTS idx_instagram_media_ts ON instagram_media(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_instagram_media_insights_artist ON instagram_media_insights(artist_id);
CREATE INDEX IF NOT EXISTS idx_instagram_media_insights_date ON instagram_media_insights(date DESC);
CREATE INDEX IF NOT EXISTS idx_instagram_media_insights_media_date ON instagram_media_insights(media_id, date DESC);
