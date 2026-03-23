-- 1. Création de la base de données spotify_etl (si elle n'existe pas)
SELECT 'CREATE DATABASE spotify_etl'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'spotify_etl')\gexec

-- 2. Connexion à la nouvelle base
\c spotify_etl

-- ============================================================
-- 3. Tables SaaS multi-tenant (doivent être créées en premier)
-- ============================================================

CREATE TABLE IF NOT EXISTS saas_artists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    tier VARCHAR(20) NOT NULL DEFAULT 'basic'
        CHECK (tier IN ('basic', 'premium')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artist_credentials (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL REFERENCES saas_artists(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    token_encrypted TEXT,
    extra_config JSONB,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, platform)
);

-- ============================================================
-- 4. Tables Spotify API (core)
-- ============================================================

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
    artist_id INTEGER DEFAULT 1 REFERENCES saas_artists(id),
    track_id VARCHAR(50) NOT NULL,
    track_name VARCHAR(255) NOT NULL,
    popularity INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date DATE DEFAULT CURRENT_DATE,
    UNIQUE(artist_id, track_id, date)
);

CREATE TABLE IF NOT EXISTS artist_history (
    id SERIAL PRIMARY KEY,
    artist_id VARCHAR(50) REFERENCES artists(artist_id),
    followers INTEGER DEFAULT 0,
    popularity INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 5. Tables SoundCloud (pas de fichier schema dédié)
-- ============================================================

CREATE TABLE IF NOT EXISTS soundcloud_tracks_daily (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER DEFAULT 1 REFERENCES saas_artists(id),
    track_id VARCHAR(50) NOT NULL,
    title VARCHAR(500),
    permalink_url TEXT,
    playback_count INTEGER DEFAULT 0,
    likes_count INTEGER DEFAULT 0,
    reposts_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    collected_at DATE DEFAULT CURRENT_DATE,
    UNIQUE(artist_id, track_id, collected_at)
);

-- ============================================================
-- 6. Tables Instagram (pas de fichier schema dédié)
-- ============================================================

CREATE TABLE IF NOT EXISTS instagram_daily_stats (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER DEFAULT 1 REFERENCES saas_artists(id),
    ig_user_id VARCHAR(50) NOT NULL,
    username VARCHAR(255),
    followers_count INTEGER DEFAULT 0,
    follows_count INTEGER DEFAULT 0,
    media_count INTEGER DEFAULT 0,
    collected_at DATE DEFAULT CURRENT_DATE,
    UNIQUE(artist_id, ig_user_id, collected_at)
);

-- ============================================================
-- 7. Index
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_saas_artists_slug ON saas_artists(slug);
CREATE INDEX IF NOT EXISTS idx_saas_artists_active ON saas_artists(active) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS idx_artist_credentials_artist ON artist_credentials(artist_id);
CREATE INDEX IF NOT EXISTS idx_track_pop_history_track ON track_popularity_history(track_id);
CREATE INDEX IF NOT EXISTS idx_track_pop_history_date ON track_popularity_history(date DESC);
CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist_id);
CREATE INDEX IF NOT EXISTS idx_soundcloud_daily_artist ON soundcloud_tracks_daily(artist_id);
CREATE INDEX IF NOT EXISTS idx_soundcloud_daily_date ON soundcloud_tracks_daily(collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_instagram_daily_artist ON instagram_daily_stats(artist_id);
CREATE INDEX IF NOT EXISTS idx_instagram_daily_date ON instagram_daily_stats(collected_at DESC);

-- ============================================================
-- 8. iMusician — revenus mensuels
-- ============================================================

CREATE TABLE IF NOT EXISTS imusician_monthly_revenue (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    revenue_eur NUMERIC(10, 2) NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_imusician_artist_month UNIQUE(artist_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_imusician_revenue_artist ON imusician_monthly_revenue(artist_id);
CREATE INDEX IF NOT EXISTS idx_imusician_revenue_period ON imusician_monthly_revenue(year DESC, month DESC);

-- ============================================================
-- 9. ML — Prédictions scoring quotidien
-- ============================================================

CREATE TABLE IF NOT EXISTS ml_song_predictions (
    id SERIAL PRIMARY KEY,
    artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
    song VARCHAR(255) NOT NULL,
    prediction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    days_since_release INTEGER,
    streams_7d INTEGER,
    streams_28d INTEGER,
    dw_probability FLOAT,
    rr_probability FLOAT,
    radio_probability FLOAT,
    dw_streams_forecast_7d INTEGER,
    rr_streams_forecast_7d INTEGER,
    model_version VARCHAR(50) DEFAULT 'v1',
    features_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_ml_prediction UNIQUE(artist_id, song, prediction_date, model_version)
);

CREATE INDEX IF NOT EXISTS idx_ml_predictions_artist ON ml_song_predictions(artist_id);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_song_date ON ml_song_predictions(artist_id, song, prediction_date DESC);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_date ON ml_song_predictions(prediction_date DESC);

-- ============================================================
-- 10. Données initiales
-- ============================================================

-- Artiste par défaut (id=1 pour les données existantes single-artist)
INSERT INTO saas_artists (id, name, slug, tier, active)
VALUES (1, 'Artist Default', 'default', 'premium', TRUE)
ON CONFLICT (slug) DO NOTHING;

-- Réinitialiser la séquence au-dessus de l'id max
SELECT setval('saas_artists_id_seq', GREATEST(1, (SELECT MAX(id) FROM saas_artists)));

-- Donnée de test track_popularity_history
INSERT INTO track_popularity_history (artist_id, track_id, track_name, popularity, date)
VALUES (1, 'test_track_001', 'Test Track Initialization', 50, CURRENT_DATE)
ON CONFLICT (artist_id, track_id, date) DO NOTHING;
