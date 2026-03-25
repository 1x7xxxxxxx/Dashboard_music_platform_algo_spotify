"""DAG YouTube Data API - Collecte manuelle.

Brick 6 : supporte artist_id dans dag_run.conf.
  - conf.artist_id fourni → credentials depuis DB pour cet artiste.
  - conf absent           → fallback sur env vars (comportement historique).
"""
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


def _on_failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {e}")


default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'on_failure_callback': _on_failure_callback,
}


def collect_youtube_data(**context):
    """Collecte les données YouTube pour tous les artistes actifs."""
    try:
        from src.collectors.youtube_collector import YouTubeCollector
        from src.database.postgres_handler import PostgresHandler
        from src.utils.credential_loader import load_platform_credentials, get_active_artists

        logger.info('=' * 70)
        logger.info('YouTube Data API — collect')
        logger.info('=' * 70)

        conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
        artist_id_conf = conf.get('artist_id')

        artists = get_active_artists(include_artist_id=artist_id_conf)
        if not artists:
            logger.info("No active artists in DB — fallback env vars (artist_id=1)")
            artists = [(1, 'default')]

        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )

        results = []
        artists_with_creds = 0
        successful_fetches = 0

        for saas_artist_id, artist_name in artists:
            logger.info(f'YouTube collect — artist_id={saas_artist_id} ({artist_name})')

            creds = load_platform_credentials(saas_artist_id, 'youtube')
            api_key = creds.get('api_key') or os.getenv('YOUTUBE_API_KEY')
            channel_id = creds.get('channel_id') or os.getenv('YOUTUBE_CHANNEL_ID')

            if not api_key or not channel_id:
                logger.warning(f'  Missing YouTube credentials for {artist_name} — skipping')
                continue

            artists_with_creds += 1
            collector = YouTubeCollector(api_key)
            data = collector.collect_all_data(channel_id=channel_id, max_videos=50, collect_comments=False)

            if data['channel_stats']:
                successful_fetches += 1
                channel_row = {**data['channel_stats'], 'artist_id': saas_artist_id}
                db.upsert_many(
                    table='youtube_channels',
                    data=[channel_row],
                    conflict_columns=['channel_id'],
                    update_columns=[
                        'artist_id', 'channel_name', 'description', 'subscriber_count',
                        'video_count', 'view_count', 'thumbnail_url', 'country', 'collected_at'
                    ]
                )

                db.execute_query(
                    """
                    INSERT INTO youtube_channel_history
                    (artist_id, channel_id, subscriber_count, video_count, view_count, collected_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        saas_artist_id,
                        data['channel_stats']['channel_id'],
                        data['channel_stats']['subscriber_count'],
                        data['channel_stats']['video_count'],
                        data['channel_stats']['view_count'],
                        data['channel_stats']['collected_at'],
                    )
                )
                logger.info(f'  Channel + history stored')

            if data['videos']:
                videos_with_artist = [{**v, 'artist_id': saas_artist_id} for v in data['videos']]
                db.upsert_many(
                    table='youtube_videos',
                    data=videos_with_artist,
                    conflict_columns=['video_id'],
                    update_columns=['artist_id', 'title', 'description', 'thumbnail_url', 'collected_at']
                )
                logger.info(f'  {len(data["videos"])} videos stored')

            if data['video_stats']:
                for stat in data['video_stats']:
                    db.execute_query(
                        """
                        INSERT INTO youtube_video_stats
                        (artist_id, video_id, view_count, like_count, comment_count, favorite_count, collected_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            saas_artist_id,
                            stat['video_id'],
                            stat['view_count'],
                            stat['like_count'],
                            stat['comment_count'],
                            stat['favorite_count'],
                            stat['collected_at'],
                        )
                    )
                    db.execute_query(
                        "UPDATE youtube_videos SET duration = %s, definition = %s WHERE video_id = %s",
                        (stat.get('duration'), stat.get('definition'), stat['video_id'])
                    )
                logger.info(f'  {len(data["video_stats"])} video stats stored')

            if data['comments']:
                db.upsert_many(
                    table='youtube_comments',
                    data=data['comments'],
                    conflict_columns=['comment_id'],
                    update_columns=['like_count', 'collected_at']
                )

            results.append({'artist': artist_name, 'videos': len(data['videos'])})

        db.close()

        if artists_with_creds > 0 and successful_fetches == 0:
            raise ValueError(
                f"YouTube API returned no channel data for any of the {artists_with_creds} "
                "configured artist(s). Check API key validity and channel IDs."
            )

        logger.info('YouTube collect done')
        return results

    except Exception as e:
        logger.error(f'YouTube collect error: {e}')
        import traceback
        traceback.print_exc()
        raise


with DAG(
    'youtube_daily',
    default_args=default_args,
    description='🎬 Collecte manuelle YouTube Data API',
    schedule_interval='0 8 * * *',  # Daily 08:00 UTC (10:00 Paris)
    start_date=datetime(2025, 1, 20),
    catchup=False,
    tags=['youtube', 'api', 'production'],
) as dag:
    
    collect_task = PythonOperator(
        task_id='collect_youtube_data',
        python_callable=collect_youtube_data,
        provide_context=True,
    )