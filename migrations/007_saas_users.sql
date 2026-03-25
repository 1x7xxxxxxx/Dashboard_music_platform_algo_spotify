-- Migration 007 — DB-based user auth (replaces YAML streamlit-authenticator)
-- Run: Get-Content migrations/007_saas_users.sql | docker exec -i postgres_spotify_airflow psql -U postgres -d spotify_etl

CREATE TABLE IF NOT EXISTS saas_users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(100)  NOT NULL UNIQUE,
    email           VARCHAR(255)  NOT NULL UNIQUE,
    password_hash   TEXT          NOT NULL,
    artist_id       INTEGER       REFERENCES saas_artists(id) ON DELETE SET NULL,
    role            VARCHAR(20)   NOT NULL DEFAULT 'artist'
                        CHECK (role IN ('admin', 'artist')),
    active          BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN saas_users.artist_id IS
    'NULL = admin (unrestricted cross-tenant access). FK to saas_artists.';
COMMENT ON COLUMN saas_users.password_hash IS
    'bcrypt hash via passlib CryptContext(schemes=["bcrypt"]).';

CREATE INDEX IF NOT EXISTS idx_saas_users_username  ON saas_users(username);
CREATE INDEX IF NOT EXISTS idx_saas_users_email     ON saas_users(email);
CREATE INDEX IF NOT EXISTS idx_saas_users_artist    ON saas_users(artist_id) WHERE artist_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_saas_users_active    ON saas_users(active) WHERE active = TRUE;
