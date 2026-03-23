"""Schéma PostgreSQL pour les tables SaaS multi-tenant."""

SAAS_SCHEMA = {
    'saas_artists': """
        CREATE TABLE IF NOT EXISTS saas_artists (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) NOT NULL UNIQUE,
            tier VARCHAR(20) NOT NULL DEFAULT 'basic'
                CHECK (tier IN ('basic', 'premium')),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_saas_artists_slug ON saas_artists(slug);
        CREATE INDEX IF NOT EXISTS idx_saas_artists_active
            ON saas_artists(active) WHERE active = TRUE;
    """,

    'artist_credentials': """
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

        CREATE INDEX IF NOT EXISTS idx_artist_credentials_artist
            ON artist_credentials(artist_id);
        CREATE INDEX IF NOT EXISTS idx_artist_credentials_platform
            ON artist_credentials(platform);
    """
}


def get_create_table_sql(table_name: str) -> str:
    """Retourne le SQL de création pour une table."""
    return SAAS_SCHEMA.get(table_name, "")


def get_all_tables() -> list:
    """Retourne la liste de toutes les tables SaaS."""
    return list(SAAS_SCHEMA.keys())
