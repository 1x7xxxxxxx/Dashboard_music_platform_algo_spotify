"""Script de diagnostic pour identifier les problèmes de collecte YouTube."""
import os
import sys
from datetime import datetime
import logging

# Configuration logging détaillé
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, '/opt/airflow')

from dotenv import load_dotenv
load_dotenv('/opt/airflow/.env')

from src.collectors.youtube_collector import YouTubeCollector
from src.database.postgres_handler import PostgresHandler


def check_environment():
    """Vérifie les variables d'environnement."""
    logger.info("="*70)
    logger.info("🔍 VÉRIFICATION ENVIRONNEMENT")
    logger.info("="*70)
    
    required_vars = {
        'YOUTUBE_API_KEY': os.getenv('YOUTUBE_API_KEY'),
        'YOUTUBE_CHANNEL_ID': os.getenv('YOUTUBE_CHANNEL_ID'),
        'DATABASE_HOST': os.getenv('DATABASE_HOST', 'postgres'),
        'DATABASE_PORT': os.getenv('DATABASE_PORT', '5432'),
        'DATABASE_NAME': os.getenv('DATABASE_NAME', 'spotify_etl'),
        'DATABASE_USER': os.getenv('DATABASE_USER', 'postgres'),
        'DATABASE_PASSWORD': os.getenv('DATABASE_PASSWORD')
    }
    
    all_ok = True
    for var, value in required_vars.items():
        if value:
            if 'PASSWORD' in var or 'KEY' in var:
                logger.info(f"✅ {var}: ***{value[-4:]}")
            else:
                logger.info(f"✅ {var}: {value}")
        else:
            logger.error(f"❌ {var}: MANQUANT")
            all_ok = False
    
    return all_ok


def check_database_connection():
    """Vérifie la connexion à la base de données."""
    logger.info("\n" + "="*70)
    logger.info("🔍 VÉRIFICATION CONNEXION DATABASE")
    logger.info("="*70)
    
    try:
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        logger.info("✅ Connexion PostgreSQL OK")
        
        # Vérifier les tables YouTube
        tables = [
            'youtube_channels',
            'youtube_channel_history',
            'youtube_videos',
            'youtube_video_stats',
            'youtube_playlists',
            'youtube_comments'
        ]
        
        logger.info("\n📊 État des tables:")
        for table in tables:
            if db.table_exists(table):
                count = db.get_table_count(table)
                logger.info(f"   ✅ {table}: {count} lignes")
            else:
                logger.error(f"   ❌ {table}: TABLE N'EXISTE PAS")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur connexion database: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_youtube_api():
    """Test de l'API YouTube."""
    logger.info("\n" + "="*70)
    logger.info("🔍 TEST API YOUTUBE")
    logger.info("="*70)
    
    api_key = os.getenv('YOUTUBE_API_KEY')
    channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
    
    if not api_key or not channel_id:
        logger.error("❌ Variables YouTube manquantes")
        return False
    
    try:
        collector = YouTubeCollector(api_key)
        
        # Test 1: Stats chaîne
        logger.info("\n📊 Test 1: Récupération stats chaîne...")
        channel_stats = collector.get_channel_stats(channel_id)
        
        if channel_stats:
            logger.info(f"   ✅ Chaîne: {channel_stats['channel_name']}")
            logger.info(f"   ✅ Abonnés: {channel_stats['subscriber_count']:,}")
            logger.info(f"   ✅ Vidéos: {channel_stats['video_count']:,}")
        else:
            logger.error("   ❌ Impossible de récupérer stats chaîne")
            return False
        
        # Test 2: Liste vidéos
        logger.info("\n📹 Test 2: Récupération vidéos (max 5)...")
        videos = collector.get_channel_videos(channel_id, max_results=5)
        
        if videos:
            logger.info(f"   ✅ {len(videos)} vidéos récupérées")
            for i, video in enumerate(videos[:3], 1):
                logger.info(f"      {i}. {video['title'][:50]}")
        else:
            logger.error("   ❌ Aucune vidéo récupérée")
            return False
        
        # Test 3: Stats vidéos
        if videos:
            logger.info("\n📊 Test 3: Récupération stats vidéos...")
            video_ids = [v['video_id'] for v in videos]
            stats = collector.get_video_stats(video_ids)
            
            if stats:
                logger.info(f"   ✅ Stats de {len(stats)} vidéos récupérées")
                for stat in stats[:3]:
                    logger.info(f"      • {stat['title'][:40]}: {stat['view_count']:,} vues")
            else:
                logger.error("   ❌ Aucune stat vidéo récupérée")
        
        # Test 4: Playlists
        logger.info("\n📋 Test 4: Récupération playlists...")
        playlists = collector.get_playlists(channel_id)
        
        if playlists:
            logger.info(f"   ✅ {len(playlists)} playlists récupérées")
            for playlist in playlists[:3]:
                logger.info(f"      • {playlist['title']}: {playlist['video_count']} vidéos")
        else:
            logger.warning("   ⚠️ Aucune playlist trouvée")
        
        logger.info("\n✅ Tous les tests API YouTube réussis")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur test API YouTube: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_insertion():
    """Test d'insertion de données dans PostgreSQL."""
    logger.info("\n" + "="*70)
    logger.info("🔍 TEST INSERTION DONNÉES")
    logger.info("="*70)
    
    api_key = os.getenv('YOUTUBE_API_KEY')
    channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
    
    try:
        # Collecter données
        logger.info("📥 Collecte de 5 vidéos pour test...")
        collector = YouTubeCollector(api_key)
        data = collector.collect_all_data(
            channel_id=channel_id,
            max_videos=5,
            collect_comments=False
        )
        
        # Connexion DB
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        # Test insertion chaîne
        if data['channel_stats']:
            logger.info("\n📊 Test insertion chaîne...")
            
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
            
            logger.info(f"   ✅ Chaîne insérée/mise à jour: {count} ligne(s)")
            
            # Vérifier l'insertion
            verify_query = "SELECT channel_name, subscriber_count FROM youtube_channels WHERE channel_id = %s"
            result = db.fetch_query(verify_query, (data['channel_stats']['channel_id'],))
            
            if result:
                logger.info(f"   ✅ Vérification: {result[0][0]} avec {result[0][1]:,} abonnés")
            else:
                logger.error("   ❌ Données non trouvées après insertion!")
        
        # Test insertion vidéos
        if data['videos']:
            logger.info(f"\n📹 Test insertion {len(data['videos'])} vidéos...")
            
            count = db.upsert_many(
                table='youtube_videos',
                data=data['videos'],
                conflict_columns=['video_id'],
                update_columns=['title', 'description', 'thumbnail_url', 'collected_at']
            )
            
            logger.info(f"   ✅ {count} vidéo(s) insérée(s)/mise(s) à jour")
            
            # Vérifier
            verify_count = db.get_table_count('youtube_videos')
            logger.info(f"   ✅ Vérification: {verify_count} vidéos dans la table")
        
        # Test insertion stats vidéos
        if data['video_stats']:
            logger.info(f"\n📊 Test insertion stats de {len(data['video_stats'])} vidéos...")
            
            inserted = 0
            for stat in data['video_stats']:
                try:
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
                    inserted += 1
                except Exception as e:
                    logger.warning(f"   ⚠️ Stat déjà existante pour {stat['video_id']}")
            
            logger.info(f"   ✅ {inserted} stat(s) insérée(s)")
            
            # Vérifier
            verify_count = db.get_table_count('youtube_video_stats')
            logger.info(f"   ✅ Vérification: {verify_count} stats dans la table")
        
        db.close()
        
        logger.info("\n✅ Tous les tests d'insertion réussis")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur test insertion: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Exécute tous les diagnostics."""
    logger.info("\n" + "🏁 DÉBUT DU DIAGNOSTIC COMPLET")
    logger.info(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        'environment': False,
        'database': False,
        'api': False,
        'insertion': False
    }
    
    # 1. Vérifier environnement
    results['environment'] = check_environment()
    
    # 2. Vérifier connexion database
    if results['environment']:
        results['database'] = check_database_connection()
    
    # 3. Tester API YouTube
    if results['environment']:
        results['api'] = test_youtube_api()
    
    # 4. Tester insertion données
    if results['environment'] and results['database'] and results['api']:
        results['insertion'] = test_data_insertion()
    
    # Résumé
    logger.info("\n" + "="*70)
    logger.info("📊 RÉSUMÉ DU DIAGNOSTIC")
    logger.info("="*70)
    
    for test, success in results.items():
        status = "✅ OK" if success else "❌ ÉCHEC"
        logger.info(f"{status} - {test.upper()}")
    
    all_ok = all(results.values())
    
    if all_ok:
        logger.info("\n🎉 Tous les tests sont réussis!")
        logger.info("   Le système devrait fonctionner correctement.")
    else:
        logger.error("\n❌ Des problèmes ont été détectés.")
        logger.error("   Consultez les logs ci-dessus pour plus de détails.")
    
    logger.info("\n🏁 FIN DU DIAGNOSTIC")
    logger.info("="*70)
    
    return all_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)