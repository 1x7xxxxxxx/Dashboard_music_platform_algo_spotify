"""PostgreSQL schema for artist_wrapped — annual Spotify for Artists metrics."""

WRAPPED_SCHEMA = {
    'artist_wrapped': """
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

        CREATE INDEX IF NOT EXISTS idx_artist_wrapped_artist
        ON artist_wrapped(artist_id);

        CREATE INDEX IF NOT EXISTS idx_artist_wrapped_year
        ON artist_wrapped(artist_id, year DESC);
    """
}


def create_wrapped_tables():
    """Create artist_wrapped table in PostgreSQL."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))

    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader

    config = config_loader.load()
    db = PostgresHandler(**config['database'])

    try:
        for table_name, sql in WRAPPED_SCHEMA.items():
            print(f"Creating {table_name}...")
            db.execute_query(sql)
            print(f"  OK: {table_name}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    create_wrapped_tables()
