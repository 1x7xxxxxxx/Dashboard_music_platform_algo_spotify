"""
Type: Sub
Depends on: postgres_handler.PostgresHandler
Persists in: PostgreSQL spotify_etl

Daily saves history. s4a_songs_global only carries a rolling 28-day saves
snapshot (no time series), so a sudden save spike on an old song cannot be
detected. This table historises the per-song saves value once a day, enabling
the long-tail "resurrection" radar (src/utils/saves_history.py).
"""

SCHEMA = {
    "s4a_song_saves_daily": """
        CREATE TABLE IF NOT EXISTS s4a_song_saves_daily (
            id              SERIAL PRIMARY KEY,
            artist_id       INTEGER NOT NULL REFERENCES saas_artists(id),
            song            VARCHAR(255) NOT NULL,
            snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
            saves           INTEGER,
            collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (artist_id, song, snapshot_date)
        )
    """,
}


def create_saves_history_tables(db) -> None:
    for _table_name, ddl in SCHEMA.items():
        db.execute_query(ddl)
