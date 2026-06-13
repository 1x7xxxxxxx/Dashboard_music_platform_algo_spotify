"""
Type: Sub
Depends on: postgres_handler.PostgresHandler
Persists in: PostgreSQL spotify_etl

Instagram media catalogue + per-post insights (Graph API /{ig-user-id}/media
and /{media-id}/insights). Account-level stats stay in instagram_daily_stats.
UNIQUE constraints include artist_id (multi-tenant); upsert conflict_columns
must match them exactly.
"""

INSTAGRAM_SCHEMA = {
    'instagram_media': """
        CREATE TABLE IF NOT EXISTS instagram_media (
            id SERIAL PRIMARY KEY,
            artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
            media_id VARCHAR(255) NOT NULL,
            caption TEXT,
            media_type VARCHAR(30),
            permalink TEXT,
            media_url TEXT,
            timestamp TIMESTAMP,
            like_count INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_instagram_media UNIQUE (artist_id, media_id)
        );

        CREATE INDEX IF NOT EXISTS idx_instagram_media_artist
        ON instagram_media(artist_id);

        CREATE INDEX IF NOT EXISTS idx_instagram_media_ts
        ON instagram_media(timestamp DESC);
    """,

    'instagram_media_insights': """
        CREATE TABLE IF NOT EXISTS instagram_media_insights (
            id SERIAL PRIMARY KEY,
            artist_id INTEGER NOT NULL DEFAULT 1 REFERENCES saas_artists(id),
            media_id VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            impressions INTEGER DEFAULT 0,
            reach INTEGER DEFAULT 0,
            engagement INTEGER DEFAULT 0,
            saved INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_instagram_media_insights
                UNIQUE (artist_id, media_id, date)
        );

        CREATE INDEX IF NOT EXISTS idx_instagram_media_insights_artist
        ON instagram_media_insights(artist_id);

        CREATE INDEX IF NOT EXISTS idx_instagram_media_insights_date
        ON instagram_media_insights(date DESC);

        CREATE INDEX IF NOT EXISTS idx_instagram_media_insights_media_date
        ON instagram_media_insights(media_id, date DESC);
    """,
}


def create_instagram_tables():
    """Create the Instagram media tables in PostgreSQL."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))

    from src.database.postgres_handler import PostgresHandler

    print("\n" + "=" * 70)
    print("📸 CRÉATION TABLES INSTAGRAM MEDIA")
    print("=" * 70 + "\n")

    db = PostgresHandler.from_env_or_config()

    try:
        for table_name, sql in INSTAGRAM_SCHEMA.items():
            print(f"📋 Création de {table_name}...")
            if db.table_exists(table_name):
                print(f"   ⚠️  Table {table_name} existe déjà")
            db.execute_query(sql)
            print(f"   ✅ Table {table_name} créée/vérifiée")

        for table_name in INSTAGRAM_SCHEMA:
            count = db.get_table_count(table_name)
            print(f"   ✅ {table_name}: {count} enregistrement(s)")

    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()

    print("\n" + "=" * 70)
    print("✅ TABLES INSTAGRAM MEDIA CRÉÉES/VÉRIFIÉES")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    create_instagram_tables()
