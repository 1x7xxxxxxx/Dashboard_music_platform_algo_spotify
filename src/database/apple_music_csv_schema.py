"""Schéma PostgreSQL simplifié pour CSV Apple Music."""

APPLE_MUSIC_CSV_SCHEMA = {
    'apple_songs_performance': """
        CREATE TABLE IF NOT EXISTS apple_songs_performance (
            id SERIAL PRIMARY KEY,
            artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
            song_name VARCHAR(255) NOT NULL,
            album_name VARCHAR(255),
            plays INTEGER DEFAULT 0,
            listeners INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(artist_id, song_name)
        );
        
        CREATE INDEX IF NOT EXISTS idx_apple_songs_perf_name 
        ON apple_songs_performance(song_name);
        
        CREATE INDEX IF NOT EXISTS idx_apple_songs_perf_plays 
        ON apple_songs_performance(plays DESC);
    """,
    
    'apple_daily_plays': """
        CREATE TABLE IF NOT EXISTS apple_daily_plays (
            id SERIAL PRIMARY KEY,
            artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
            song_name VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            plays INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(artist_id, song_name, date)
        );
        
        CREATE INDEX IF NOT EXISTS idx_apple_daily_song 
        ON apple_daily_plays(song_name);
        
        CREATE INDEX IF NOT EXISTS idx_apple_daily_date 
        ON apple_daily_plays(date DESC);
        
        CREATE INDEX IF NOT EXISTS idx_apple_daily_song_date 
        ON apple_daily_plays(song_name, date);
    """,
    
    'apple_listeners': """
        CREATE TABLE IF NOT EXISTS apple_listeners (
            id SERIAL PRIMARY KEY,
            artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
            date DATE NOT NULL,
            listeners INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(artist_id, date)
        );

        CREATE INDEX IF NOT EXISTS idx_apple_listeners_date
        ON apple_listeners(date DESC);
    """,

    'apple_songs_history': """
        CREATE TABLE IF NOT EXISTS apple_songs_history (
            id SERIAL PRIMARY KEY,
            artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
            song_name VARCHAR(255) NOT NULL,
            plays INTEGER DEFAULT 0,
            shazam_count INTEGER DEFAULT 0,
            date DATE NOT NULL DEFAULT CURRENT_DATE,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_apple_history_artist
        ON apple_songs_history(artist_id);

        CREATE INDEX IF NOT EXISTS idx_apple_history_date
        ON apple_songs_history(date DESC);
    """
}


def create_apple_music_csv_tables():
    """Crée les tables simplifiées pour CSV Apple Music."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader
    
    print("\n" + "="*70)
    print("🍎 CRÉATION TABLES APPLE MUSIC (CSV)")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db_config = config['database']
    
    db = PostgresHandler(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )
    
    try:
        for table_name, sql in APPLE_MUSIC_CSV_SCHEMA.items():
            print(f"📋 Création de {table_name}...")
            db.execute_query(sql)
            print(f"   ✅ Table {table_name} créée")
        
        print("\n🔍 Vérification...")
        for table_name in APPLE_MUSIC_CSV_SCHEMA.keys():
            count = db.get_table_count(table_name)
            print(f"   ✅ {table_name}: {count} enregistrement(s)")
        
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
    
    db.close()
    
    print("\n" + "="*70)
    print("✅ TABLES APPLE MUSIC (CSV) CRÉÉES")
    print("="*70 + "\n")


if __name__ == "__main__":
    create_apple_music_csv_tables()