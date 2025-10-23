"""Schéma PostgreSQL pour Spotify API."""

SPOTIFY_SCHEMA = {
    'artists': """
        CREATE TABLE IF NOT EXISTS artists (
            artist_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            followers INTEGER DEFAULT 0,
            popularity INTEGER DEFAULT 0,
            genres TEXT[],
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name);
        CREATE INDEX IF NOT EXISTS idx_artists_popularity ON artists(popularity DESC);
    """,
    
    'artist_history': """
        CREATE TABLE IF NOT EXISTS artist_history (
            id SERIAL PRIMARY KEY,
            artist_id VARCHAR(50) REFERENCES artists(artist_id),
            followers INTEGER DEFAULT 0,
            popularity INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_artist_history_artist ON artist_history(artist_id);
        CREATE INDEX IF NOT EXISTS idx_artist_history_date ON artist_history(collected_at DESC);
    """,
    
    'tracks': """
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
        
        CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist_id);
        CREATE INDEX IF NOT EXISTS idx_tracks_popularity ON tracks(popularity DESC);
        CREATE INDEX IF NOT EXISTS idx_tracks_name ON tracks(track_name);
    """,
    
    'track_popularity_history': """
        CREATE TABLE IF NOT EXISTS track_popularity_history (
            id SERIAL PRIMARY KEY,
            track_id VARCHAR(50) REFERENCES tracks(track_id),
            track_name VARCHAR(255) NOT NULL,
            popularity INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date DATE DEFAULT CURRENT_DATE,
            UNIQUE(track_id, date)
        );
        
        CREATE INDEX IF NOT EXISTS idx_track_pop_history_track ON track_popularity_history(track_id);
        CREATE INDEX IF NOT EXISTS idx_track_pop_history_date ON track_popularity_history(date DESC);
        CREATE INDEX IF NOT EXISTS idx_track_pop_history_track_date ON track_popularity_history(track_id, date);
    """
}


def get_create_table_sql(table_name: str) -> str:
    """Retourne le SQL de création pour une table."""
    return SPOTIFY_SCHEMA.get(table_name, "")


def get_all_tables() -> list:
    """Retourne la liste de toutes les tables Spotify."""
    return list(SPOTIFY_SCHEMA.keys())