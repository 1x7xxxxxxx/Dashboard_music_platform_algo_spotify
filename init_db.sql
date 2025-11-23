-- 1. Création de la base de données spotify_etl (si elle n'existe pas)
SELECT 'CREATE DATABASE spotify_etl'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'spotify_etl')\gexec

-- 2. Connexion à la nouvelle base
\c spotify_etl

-- 3. Création des tables
CREATE TABLE IF NOT EXISTS artists (
    artist_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    followers INTEGER DEFAULT 0,
    popularity INTEGER DEFAULT 0,
    genres TEXT[],
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tracks (
    track_id VARCHAR(50) PRIMARY KEY,
    track_name VARCHAR(255) NOT NULL,
    artist_id VARCHAR(50) REFERENCES artists(artist_id),
    popularity INTEGER DEFAULT 0,
    duration_ms INTEGER,
    explicit BOOLEAN DEFAULT FALSE,
    album_name VARCHAR(255),
    release_date DATE,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS track_popularity_history (
    id SERIAL PRIMARY KEY,
    track_id VARCHAR(50) NOT NULL,
    track_name VARCHAR(255) NOT NULL,
    popularity INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date DATE DEFAULT CURRENT_DATE,
    UNIQUE(track_id, date)
);

CREATE TABLE IF NOT EXISTS artist_history (
    id SERIAL PRIMARY KEY,
    artist_id VARCHAR(50) REFERENCES artists(artist_id),
    followers INTEGER DEFAULT 0,
    popularity INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Création des index
CREATE INDEX IF NOT EXISTS idx_track_pop_history_track ON track_popularity_history(track_id);
CREATE INDEX IF NOT EXISTS idx_track_pop_history_date ON track_popularity_history(date DESC);
CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist_id);

-- 5. Donnée de test (Optionnel)
INSERT INTO track_popularity_history (track_id, track_name, popularity, date)
VALUES ('test_track_001', 'Test Track Initialization', 50, CURRENT_DATE)
ON CONFLICT (track_id, date) DO NOTHING;