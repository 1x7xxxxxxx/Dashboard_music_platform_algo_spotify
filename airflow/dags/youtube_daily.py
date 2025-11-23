"""DAG YouTube Data API - Collecte manuelle."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
import logging

sys.path.insert(0, '/opt/airflow')

#Déjà lecture via docker-compose.yml
#from dotenv import load_dotenv
#load_dotenv('/opt/airflow/.env')

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
}


def collect_youtube_data(**context):
    """Collecte les données YouTube."""
    try:
        from src.collectors.youtube_collector import YouTubeCollector
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('='*70)
        logger.info('🎬 COLLECTE YOUTUBE DATA API')
        logger.info('='*70)
        
        # Config YouTube
        api_key = os.getenv('YOUTUBE_API_KEY')
        channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
        
        if not api_key or not channel_id:
            logger.error('❌ YOUTUBE_API_KEY ou YOUTUBE_CHANNEL_ID manquant')
            raise ValueError('Configuration YouTube manquante')
        
        # Collecte
        collector = YouTubeCollector(api_key)
        data = collector.collect_all_data(
            channel_id=channel_id,
            max_videos=50,
            collect_comments=False  # Mettre True pour collecter commentaires (coûteux)
        )
        
        # Connexion DB
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        # Stocker stats de chaîne
        if data['channel_stats']:
            logger.info('📊 Stockage stats chaîne...')
            
            # Upsert chaîne
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
            logger.info(f'   ✅ Chaîne stockée')
            
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
            logger.info(f'   ✅ Historique chaîne stocké')
        
        # Stocker vidéos
        if data['videos']:
            logger.info(f'📹 Stockage {len(data["videos"])} vidéos...')
            
            count = db.upsert_many(
                table='youtube_videos',
                data=data['videos'],
                conflict_columns=['video_id'],
                update_columns=[
                    'title', 'description', 'thumbnail_url', 'collected_at'
                ]
            )
            logger.info(f'   ✅ {count} vidéos stockées')
        
        # Stocker stats vidéos
        if data['video_stats']:
            logger.info(f'📊 Stockage stats vidéos...')
            
            # Insérer historique (pas d'upsert, on garde l'historique)
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
            
            # Mettre à jour duration et definition dans youtube_videos
            for stat in data['video_stats']:
                db.execute_query(
                    """
                    UPDATE youtube_videos 
                    SET duration = %s, definition = %s
                    WHERE video_id = %s
                    """,
                    (stat.get('duration'), stat.get('definition'), stat['video_id'])
                )
            
            logger.info(f'   ✅ {len(data["video_stats"])} stats vidéos stockées')
        
        # Stocker playlists
        if data['playlists']:
            logger.info(f'📋 Stockage {len(data["playlists"])} playlists...')
            
            count = db.upsert_many(
                table='youtube_playlists',
                data=data['playlists'],
                conflict_columns=['playlist_id'],
                update_columns=[
                    'title', 'description', 'video_count', 
                    'thumbnail_url', 'collected_at'
                ]
            )
            logger.info(f'   ✅ {count} playlists stockées')
        
        # Stocker commentaires (si collectés)
        if data['comments']:
            logger.info(f'💬 Stockage {len(data["comments"])} commentaires...')
            
            count = db.upsert_many(
                table='youtube_comments',
                data=data['comments'],
                conflict_columns=['comment_id'],
                update_columns=['like_count', 'collected_at']
            )
            logger.info(f'   ✅ {count} commentaires stockés')
        
        db.close()
        
        logger.info('\n' + '='*70)
        logger.info('✅ COLLECTE YOUTUBE TERMINÉE')
        logger.info('='*70)
        logger.info(f'📊 Résumé:')
        logger.info(f'   • Chaîne: {data["channel_stats"]["channel_name"]}')
        logger.info(f'   • Abonnés: {data["channel_stats"]["subscriber_count"]:,}')
        logger.info(f'   • Vidéos: {len(data["videos"])}')
        logger.info(f'   • Playlists: {len(data["playlists"])}')
        logger.info(f'   • Commentaires: {len(data["comments"])}')
        logger.info('='*70)
        
        return {
            'channel_name': data['channel_stats']['channel_name'],
            'videos_count': len(data['videos']),
            'playlists_count': len(data['playlists'])
        }
        
    except Exception as e:
        logger.error(f'❌ Erreur collecte YouTube: {e}')
        import traceback
        traceback.print_exc()
        raise


with DAG(
    'youtube_daily',
    default_args=default_args,
    description='🎬 Collecte manuelle YouTube Data API',
    schedule_interval=None,  # Déclenchement manuel uniquement
    start_date=datetime(2025, 1, 20),
    catchup=False,
    tags=['youtube', 'api', 'production'],
) as dag:
    
    collect_task = PythonOperator(
        task_id='collect_youtube_data',
        python_callable=collect_youtube_data,
        provide_context=True,
    )