"""Schéma PostgreSQL pour YouTube Data API v3."""

YOUTUBE_SCHEMA = {
    'youtube_channels': """
        CREATE TABLE IF NOT EXISTS youtube_channels (
            id SERIAL PRIMARY KEY,
            channel_id VARCHAR(255) NOT NULL UNIQUE,
            channel_name VARCHAR(500),
            description TEXT,
            published_at TIMESTAMP,
            subscriber_count INTEGER DEFAULT 0,
            video_count INTEGER DEFAULT 0,
            view_count BIGINT DEFAULT 0,
            thumbnail_url TEXT,
            country VARCHAR(10),
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_youtube_channels_id 
        ON youtube_channels(channel_id);
        
        CREATE INDEX IF NOT EXISTS idx_youtube_channels_collected 
        ON youtube_channels(collected_at DESC);
    """,
    
    'youtube_channel_history': """
        CREATE TABLE IF NOT EXISTS youtube_channel_history (
            id SERIAL PRIMARY KEY,
            channel_id VARCHAR(255) NOT NULL,
            subscriber_count INTEGER DEFAULT 0,
            video_count INTEGER DEFAULT 0,
            view_count BIGINT DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (channel_id) REFERENCES youtube_channels(channel_id) ON DELETE CASCADE
        );
        
        CREATE INDEX IF NOT EXISTS idx_youtube_channel_history_channel 
        ON youtube_channel_history(channel_id);
        
        CREATE INDEX IF NOT EXISTS idx_youtube_channel_history_date 
        ON youtube_channel_history(collected_at DESC);
    """,
    
    'youtube_videos': """
        CREATE TABLE IF NOT EXISTS youtube_videos (
            id SERIAL PRIMARY KEY,
            video_id VARCHAR(255) NOT NULL UNIQUE,
            channel_id VARCHAR(255) NOT NULL,
            title TEXT,
            description TEXT,
            published_at TIMESTAMP,
            thumbnail_url TEXT,
            duration VARCHAR(50),
            definition VARCHAR(10),
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (channel_id) REFERENCES youtube_channels(channel_id) ON DELETE CASCADE,
            UNIQUE(video_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_youtube_videos_id 
        ON youtube_videos(video_id);
        
        CREATE INDEX IF NOT EXISTS idx_youtube_videos_channel 
        ON youtube_videos(channel_id);
        
        CREATE INDEX IF NOT EXISTS idx_youtube_videos_published 
        ON youtube_videos(published_at DESC);
    """,
    
    'youtube_video_stats': """
        CREATE TABLE IF NOT EXISTS youtube_video_stats (
            id SERIAL PRIMARY KEY,
            video_id VARCHAR(255) NOT NULL,
            view_count BIGINT DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            favorite_count INTEGER DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES youtube_videos(video_id) ON DELETE CASCADE
        );
        
        CREATE INDEX IF NOT EXISTS idx_youtube_video_stats_video 
        ON youtube_video_stats(video_id);
        
        CREATE INDEX IF NOT EXISTS idx_youtube_video_stats_date 
        ON youtube_video_stats(collected_at DESC);
        
        CREATE INDEX IF NOT EXISTS idx_youtube_video_stats_video_date 
        ON youtube_video_stats(video_id, collected_at DESC);
    """,
    
    'youtube_playlists': """
        CREATE TABLE IF NOT EXISTS youtube_playlists (
            id SERIAL PRIMARY KEY,
            playlist_id VARCHAR(255) NOT NULL UNIQUE,
            channel_id VARCHAR(255) NOT NULL,
            title TEXT,
            description TEXT,
            video_count INTEGER DEFAULT 0,
            published_at TIMESTAMP,
            thumbnail_url TEXT,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (channel_id) REFERENCES youtube_channels(channel_id) ON DELETE CASCADE,
            UNIQUE(playlist_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_youtube_playlists_id 
        ON youtube_playlists(playlist_id);
        
        CREATE INDEX IF NOT EXISTS idx_youtube_playlists_channel 
        ON youtube_playlists(channel_id);
    """,
    
    'youtube_comments': """
        CREATE TABLE IF NOT EXISTS youtube_comments (
            id SERIAL PRIMARY KEY,
            comment_id VARCHAR(255) NOT NULL UNIQUE,
            video_id VARCHAR(255) NOT NULL,
            author VARCHAR(500),
            text TEXT,
            like_count INTEGER DEFAULT 0,
            published_at TIMESTAMP,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES youtube_videos(video_id) ON DELETE CASCADE,
            UNIQUE(comment_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_youtube_comments_video 
        ON youtube_comments(video_id);
        
        CREATE INDEX IF NOT EXISTS idx_youtube_comments_published 
        ON youtube_comments(published_at DESC);
    """
}


def create_youtube_tables():
    """Crée les tables YouTube dans PostgreSQL."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader
    
    print("\n" + "="*70)
    print("🎬 CRÉATION TABLES YOUTUBE")
    print("="*70 + "\n")
    
    config = config_loader.load()
    db = PostgresHandler(**config['database'])
    
    try:
        for table_name, sql in YOUTUBE_SCHEMA.items():
            print(f"📋 Création de {table_name}...")
            db.execute_query(sql)
            print(f"   ✅ Table {table_name} créée")
        
        print("\n🔍 Vérification...")
        for table_name in YOUTUBE_SCHEMA.keys():
            count = db.get_table_count(table_name)
            print(f"   ✅ {table_name}: {count} enregistrement(s)")
    
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
    
    db.close()
    
    print("\n" + "="*70)
    print("✅ TABLES YOUTUBE CRÉÉES")
    print("="*70 + "\n")


if __name__ == "__main__":
    create_youtube_tables()