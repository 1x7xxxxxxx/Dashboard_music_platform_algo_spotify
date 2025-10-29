"""Test manuel de collecte YouTube - Bypass Airflow."""
import sys
sys.path.insert(0, '.')

import os
from dotenv import load_dotenv
load_dotenv()

from src.collectors.youtube_collector import YouTubeCollector
from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

print("\n" + "="*70)
print("🧪 TEST MANUEL COLLECTE YOUTUBE")
print("="*70 + "\n")

# 1. Vérifier les credentials
api_key = os.getenv('YOUTUBE_API_KEY')
channel_id = os.getenv('YOUTUBE_CHANNEL_ID')

if not api_key or not channel_id:
    print("❌ Credentials manquants dans .env")
    exit(1)

print(f"✅ API Key: {api_key[:10]}...")
print(f"✅ Channel ID: {channel_id}\n")

try:
    # 2. Initialiser le collector
    print("📊 Initialisation du collector...")
    collector = YouTubeCollector(api_key)
    print("✅ Collector initialisé\n")
    
    # 3. Collecter les données
    print("🔄 Collecte en cours...")
    data = collector.collect_all_data(
        channel_id=channel_id,
        max_videos=10,  # Limiter à 10 vidéos pour le test
        collect_comments=False
    )
    
    print("\n" + "="*70)
    print("📊 RÉSULTATS DE LA COLLECTE")
    print("="*70 + "\n")
    
    if data['channel_stats']:
        print(f"✅ Chaîne: {data['channel_stats']['channel_name']}")
        print(f"   Abonnés: {data['channel_stats']['subscriber_count']}")
        print(f"   Vidéos: {data['channel_stats']['video_count']}")
    else:
        print("❌ Aucune stat de chaîne")
    
    print(f"\n📹 Vidéos collectées: {len(data['videos'])}")
    print(f"📊 Stats vidéos: {len(data['video_stats'])}")
    print(f"📋 Playlists: {len(data['playlists'])}")
    print(f"💬 Commentaires: {len(data['comments'])}")
    
    # 4. Stocker en base
    if data['channel_stats'] or data['videos']:
        print("\n" + "="*70)
        print("💾 STOCKAGE EN BASE")
        print("="*70 + "\n")
        
        config = config_loader.load()
        db = PostgresHandler(**config['database'])
        
        # Stocker chaîne
        if data['channel_stats']:
            print("📊 Stockage stats chaîne...")
            try:
                count = db.upsert_many(
                    table='youtube_channels',
                    data=[data['channel_stats']],
                    conflict_columns=['channel_id'],
                    update_columns=[
                        'channel_name', 'description', 'subscriber_count',
                        'video_count', 'view_count', 'thumbnail_url', 
                        'country', 'collected_at'
                    ]
                )
                print(f"   ✅ {count} chaîne(s) stockée(s)")
                
                # Historique
                history_data = {
                    'channel_id': data['channel_stats']['channel_id'],
                    'subscriber_count': data['channel_stats']['subscriber_count'],
                    'video_count': data['channel_stats']['video_count'],
                    'view_count': data['channel_stats']['view_count'],
                    'collected_at': data['channel_stats']['collected_at']
                }
                
                db.execute_query(
                    """
                    INSERT INTO youtube_channel_history 
                    (channel_id, subscriber_count, video_count, view_count, collected_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        history_data['channel_id'],
                        history_data['subscriber_count'],
                        history_data['video_count'],
                        history_data['view_count'],
                        history_data['collected_at']
                    )
                )
                print(f"   ✅ Historique stocké")
                
            except Exception as e:
                print(f"   ❌ Erreur: {e}")
        
        # Stocker vidéos
        if data['videos']:
            print(f"\n📹 Stockage {len(data['videos'])} vidéos...")
            try:
                count = db.upsert_many(
                    table='youtube_videos',
                    data=data['videos'],
                    conflict_columns=['video_id'],
                    update_columns=['title', 'description', 'thumbnail_url', 'collected_at']
                )
                print(f"   ✅ {count} vidéo(s) stockée(s)")
            except Exception as e:
                print(f"   ❌ Erreur: {e}")
        
        # Stocker stats vidéos
        if data['video_stats']:
            print(f"\n📊 Stockage stats vidéos...")
            try:
                for stat in data['video_stats']:
                    db.execute_query(
                        """
                        INSERT INTO youtube_video_stats 
                        (video_id, view_count, like_count, comment_count, 
                         favorite_count, collected_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            stat['video_id'],
                            stat['view_count'],
                            stat['like_count'],
                            stat['comment_count'],
                            stat['favorite_count'],
                            stat['collected_at']
                        )
                    )
                    
                    # Mettre à jour duration et definition
                    db.execute_query(
                        """
                        UPDATE youtube_videos 
                        SET duration = %s, definition = %s
                        WHERE video_id = %s
                        """,
                        (stat.get('duration'), stat.get('definition'), stat['video_id'])
                    )
                
                print(f"   ✅ {len(data['video_stats'])} stats stockées")
            except Exception as e:
                print(f"   ❌ Erreur: {e}")
        
        db.close()
        
        print("\n" + "="*70)
        print("✅ TEST TERMINÉ AVEC SUCCÈS")
        print("="*70)
        print("\nVérifier les données:")
        print("  python check_youtube_data.py")
    else:
        print("\n⚠️  Aucune donnée à stocker")

except Exception as e:
    print(f"\n❌ ERREUR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70 + "\n")