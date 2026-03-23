import sys
import os
import logging
from pathlib import Path

# Setup des chemins
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.utils.config_loader import config_loader
from src.collectors.youtube_collector import YouTubeCollector
from src.database.postgres_handler import PostgresHandler

# Config logs pour voir tout ce qui se passe
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_ingestion():
    print("\n" + "="*60)
    print("🐞 DEBUG YOUTUBE INGESTION")
    print("="*60)

    # 1. Config
    config = config_loader.load()
    api_key = config['youtube']['api_key']
    # Force l'ID de ta chaîne si celui du config est mauvais
    channel_id = "UCDpjL6K1yoGdCm4M3PEdskg" 
    
    print(f"🔑 API Key: {api_key[:5]}...")
    print(f"📺 Channel ID: {channel_id}")

    # 2. Collecte
    collector = YouTubeCollector(api_key)
    print("\n📡 Récupération des vidéos via API...")
    
    # On force la récupération de 10 vidéos pour tester
    videos = collector.get_channel_videos(channel_id, max_results=10)
    
    print(f"📦 Vidéos trouvées : {len(videos)}")
    
    if not videos:
        print("❌ PROBLÈME : L'API renvoie 0 vidéos. Vérifiez l'ID de la chaîne ou le quota.")
        return

    print(f"👀 Exemple de vidéo : {videos[0]['title']} (ID: {videos[0]['video_id']})")

    # 3. Insertion BDD
    print("\n💾 Tentative d'insertion en base...")
    db = PostgresHandler(**config['database'])
    
    try:
        # Test d'insertion dans youtube_videos
        count = db.upsert_many(
            table='youtube_videos',
            data=videos,
            conflict_columns=['video_id'],
            update_columns=['title', 'description', 'thumbnail_url', 'collected_at']
        )
        print(f"✅ {count} vidéos insérées/mises à jour dans 'youtube_videos'.")
        
        # Récupération des stats (Durée, Vues...)
        video_ids = [v['video_id'] for v in videos]
        stats = collector.get_video_stats(video_ids)
        
        print(f"📊 Stats récupérées : {len(stats)}")
        
        # Test d'insertion des stats et mise à jour durée
        for stat in stats:
            # Update Duration
            db.execute_query(
                "UPDATE youtube_videos SET duration = %s WHERE video_id = %s",
                (stat.get('duration'), stat['video_id'])
            )
            
            # Insert History
            db.execute_query(
                """INSERT INTO youtube_video_stats 
                   (video_id, view_count, like_count, comment_count, collected_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (stat['video_id'], stat['view_count'], stat['like_count'], stat['comment_count'], stat['collected_at'])
            )
        
        print(f"✅ Stats et Durées mises à jour.")

    except Exception as e:
        print(f"❌ ERREUR SQL : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    debug_ingestion()