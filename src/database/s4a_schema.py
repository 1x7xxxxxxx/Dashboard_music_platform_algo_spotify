"""Schéma PostgreSQL pour Spotify for Artists."""

S4A_SCHEMA = {
    's4a_songs_global': """
        CREATE TABLE IF NOT EXISTS s4a_songs_global (
            id SERIAL PRIMARY KEY,
            song VARCHAR(255) NOT NULL,
            listeners INTEGER DEFAULT 0,
            streams INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0,
            release_date DATE,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(song)
        );
        
        CREATE INDEX IF NOT EXISTS idx_s4a_songs_song ON s4a_songs_global(song);
        CREATE INDEX IF NOT EXISTS idx_s4a_songs_streams ON s4a_songs_global(streams DESC);
    """,
    
    's4a_song_timeline': """
        CREATE TABLE IF NOT EXISTS s4a_song_timeline (
            id SERIAL PRIMARY KEY,
            song VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            streams INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(song, date)
        );
        
        CREATE INDEX IF NOT EXISTS idx_s4a_timeline_song ON s4a_song_timeline(song);
        CREATE INDEX IF NOT EXISTS idx_s4a_timeline_date ON s4a_song_timeline(date DESC);
        CREATE INDEX IF NOT EXISTS idx_s4a_timeline_song_date ON s4a_song_timeline(song, date);
    """,
    
    's4a_audience': """
        CREATE TABLE IF NOT EXISTS s4a_audience (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            listeners INTEGER DEFAULT 0,
            streams INTEGER DEFAULT 0,
            followers INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date)
        );
        
        CREATE INDEX IF NOT EXISTS idx_s4a_audience_date ON s4a_audience(date DESC);
    """
}


def get_create_table_sql(table_name: str) -> str:
    """Retourne le SQL de création pour une table."""
    return S4A_SCHEMA.get(table_name, "")


def get_all_tables() -> list:
    """Retourne la liste de toutes les tables S4A."""
    return list(S4A_SCHEMA.keys())