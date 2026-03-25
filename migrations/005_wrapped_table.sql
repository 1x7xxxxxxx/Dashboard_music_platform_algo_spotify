-- Migration 005 — Create artist_wrapped table (Data Wrapped feature)
-- Run: Get-Content migrations/005_wrapped_table.sql | docker exec -i postgres_spotify_airflow psql -U postgres -d spotify_etl

CREATE TABLE IF NOT EXISTS artist_wrapped (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    year INTEGER NOT NULL,
    listeners BIGINT,
    streams BIGINT,
    hours_listened DECIMAL(14, 1),
    countries INTEGER,
    listener_gain INTEGER,
    stream_gain BIGINT,
    save_gain INTEGER,
    playlist_add_gain INTEGER,
    saves BIGINT,
    playlist_adds BIGINT,
    top_artist_name VARCHAR(255),
    top_artist_fan_pct DECIMAL(5, 2),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_artist_wrapped_year UNIQUE(artist_id, year)
);

CREATE INDEX IF NOT EXISTS idx_artist_wrapped_artist ON artist_wrapped(artist_id);
CREATE INDEX IF NOT EXISTS idx_artist_wrapped_year ON artist_wrapped(artist_id, year DESC);
