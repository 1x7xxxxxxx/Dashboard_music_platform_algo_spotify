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
from src.utils.dag_timeouts import dagrun_timeout_for

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
        from src.utils.safe_error import safe_error
        logger.error(f"Failure callback error: {safe_error(e)}")


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
        from src.utils.safe_error import safe_error
        from src.utils.dag_run_logger import (
            record_tenant_failure, record_tenant_skip, record_tenant_success,
        )

        logger.info('=' * 70)
        logger.info('YouTube Data API — collect')
        logger.info('=' * 70)

        conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
        artist_id_conf = conf.get('artist_id')
        run_id = context.get('run_id', '') if context else ''

        artists = get_active_artists(include_artist_id=artist_id_conf)
        if not artists:
            # An empty list now means EXACTLY one thing (credential_loader raises on a
            # read failure and on an unknown artist_id): the deployment has no active
            # tenant. The legacy single-tenant fallback borrowed the admin's env
            # identity, so it is opt-in and explicit — never a silent default.
            if os.getenv('LEGACY_SINGLE_TENANT') == '1':
                logger.info("No active artist — LEGACY_SINGLE_TENANT=1, using env identity as tenant 1")
                artists = [(1, 'default')]
            else:
                logger.info("No active artist in DB — nothing to collect.")
                return

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
        per_artist_errors = []  # multi-tenant isolation: one bad tenant must not abort the fleet

        for saas_artist_id, artist_name in artists:
            logger.info(f'YouTube collect — artist_id={saas_artist_id} ({artist_name})')

            creds = load_platform_credentials(saas_artist_id, 'youtube')
            # App credential (admin-owned, shared): env fallback is the central-app
            # model (ADR-006) and stays.
            api_key = creds.get('api_key') or os.getenv('YOUTUBE_API_KEY')
            # TENANT IDENTITY: no fallback, ever. YOUTUBE_CHANNEL_ID holds the ADMIN's
            # channel, so falling back on it collected the admin's videos and wrote
            # them under this artist's artist_id. An empty string counts as absent.
            channel_id = (creds.get('channel_id') or '').strip()

            # Every branch below leaves a row in etl_run_log. Absence of a row is what
            # made that ledger unable to answer "did collection run for this tenant?" —
            # Benken's YouTube failed two nights running with no surface saying so.
            if not api_key:
                logger.warning(f'  YouTube app credential missing (YOUTUBE_API_KEY) — '
                               f'skipping {artist_name}; admin action required')
                record_tenant_skip('youtube_daily', saas_artist_id, 'youtube',
                                   'shared YouTube app not configured (admin action)', run_id)
                continue
            if not channel_id:
                logger.info(f'  {artist_name} (id={saas_artist_id}) has no YouTube '
                            'channel_id — not connected, skipping')
                record_tenant_skip('youtube_daily', saas_artist_id, 'youtube',
                                   'no YouTube channel_id declared', run_id)
                continue

            artists_with_creds += 1
            try:
                collector = YouTubeCollector(api_key)
                # 200 (not 50): older releases (e.g. a remix) get pushed past the 50 most-recent
                # uploads by frequent content (DJ sets) and were never collected → unmappable.
                data = collector.collect_all_data(channel_id=channel_id, max_videos=200, collect_comments=False)

                if data['channel_stats']:
                    successful_fetches += 1
                    channel_row = {**data['channel_stats'], 'artist_id': saas_artist_id}
                    # Conflict key is (artist_id, channel_id) since migration 064, and
                    # artist_id is NOT in update_columns: a row never changes owner.
                    db.upsert_many(
                        table='youtube_channels',
                        data=[channel_row],
                        conflict_columns=['artist_id', 'channel_id'],
                        update_columns=[
                            'channel_name', 'description', 'subscriber_count',
                            'video_count', 'view_count', 'thumbnail_url', 'country', 'collected_at'
                        ]
                    )

                    db.execute_query(
                        """
                        INSERT INTO youtube_channel_history
                        (artist_id, channel_id, subscriber_count, video_count, view_count, collected_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (artist_id, channel_id, (collected_at::date))
                        DO UPDATE SET
                            subscriber_count = EXCLUDED.subscriber_count,
                            video_count = EXCLUDED.video_count,
                            view_count = EXCLUDED.view_count,
                            collected_at = EXCLUDED.collected_at
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
                    logger.info('  Channel + history stored')

                if data['videos']:
                    videos_with_artist = [{**v, 'artist_id': saas_artist_id} for v in data['videos']]
                    db.upsert_many(
                        table='youtube_videos',
                        data=videos_with_artist,
                        conflict_columns=['artist_id', 'video_id'],
                        update_columns=['title', 'description', 'thumbnail_url', 'collected_at']
                    )
                    logger.info(f'  {len(data["videos"])} videos stored')

                if data['video_stats']:
                    stats_rows = [
                        {
                            'artist_id': saas_artist_id,
                            'video_id': stat['video_id'],
                            'view_count': stat['view_count'],
                            'like_count': stat['like_count'],
                            'comment_count': stat['comment_count'],
                            'favorite_count': stat['favorite_count'],
                            'collected_at': stat['collected_at'],
                        }
                        for stat in data['video_stats']
                    ]
                    db.upsert_many(
                        table='youtube_video_stats',
                        data=stats_rows,
                        conflict_columns=['artist_id', 'video_id', '(collected_at::date)'],
                        update_columns=['view_count', 'like_count', 'comment_count', 'favorite_count', 'collected_at']
                    )
                    for stat in data['video_stats']:
                        # Scoped by artist_id: without it this wrote across tenant
                        # boundaries from inside a per-artist loop.
                        db.execute_query(
                            "UPDATE youtube_videos SET duration = %s, definition = %s "
                            "WHERE video_id = %s AND artist_id = %s",
                            (stat.get('duration'), stat.get('definition'),
                             stat['video_id'], saas_artist_id)
                        )
                    logger.info(f'  {len(data["video_stats"])} video stats stored')

                if data['comments']:
                    # artist_id EXPLICITE : youtube_comments.artist_id porte
                    # `NOT NULL DEFAULT 1`. Le collecteur ne le pose pas, donc sans
                    # cette ligne les commentaires de tout locataire atterriraient
                    # chez l'admin (même classe que track_popularity_history).
                    # Dormant aujourd'hui (collect_comments=False), corrigé quand même.
                    comments_with_artist = [
                        {**c, 'artist_id': saas_artist_id} for c in data['comments']
                    ]
                    db.upsert_many(
                        table='youtube_comments',
                        data=comments_with_artist,
                        conflict_columns=['comment_id'],
                        update_columns=['like_count', 'collected_at']
                    )

                record_tenant_success('youtube_daily', saas_artist_id, 'youtube',
                                      len(data['videos']), run_id)
                results.append({'artist': artist_name, 'videos': len(data['videos'])})
            except Exception as e:
                # Per-artist isolation: a bad channel_id (404 playlistNotFound) or a
                # per-tenant API error must NOT abort collection for the other artists.
                # The collector still raises (project rule #6); the DAG loop absorbs it
                # per-tenant and the task fails below only if EVERY artist failed.
                # safe_error, NOT {e} / str(e) — an HttpError repr embeds the request URI,
                # so both of these lines wrote the YouTube API key into the task log in
                # clear (measured in production 2026-08-23), and per_artist_errors is
                # forwarded into the WARNING summary below.
                logger.error(
                    f'  YouTube collect failed for artist_id={saas_artist_id} '
                    f'({artist_name}): {safe_error(e)}'
                )
                per_artist_errors.append((saas_artist_id, artist_name, safe_error(e, limit=200)))
                record_tenant_failure('youtube_daily', saas_artist_id, 'youtube', e, run_id)
                continue

        db.close()

        if per_artist_errors:
            summary = '; '.join(f'{aid}/{name}: {err}' for aid, name, err in per_artist_errors)
            logger.warning(f'YouTube: {len(per_artist_errors)} artist(s) failed (isolated, continued): {summary}')

        # Fail the task only if EVERY configured artist failed — a single healthy tenant
        # keeps the run green so one broken channel can't blank the whole fleet's data.
        if artists_with_creds > 0 and successful_fetches == 0:
            raise ValueError(
                f"YouTube API returned no channel data for any of the {artists_with_creds} "
                f"configured artist(s). Per-artist errors: "
                + '; '.join(f'{aid}/{name}: {err}' for aid, name, err in per_artist_errors)
            )

        logger.info('YouTube collect done')
        return results

    except Exception as e:
        logger.error(f'YouTube collect error: {safe_error(e)}')
        import traceback
        traceback.print_exc()
        raise


with DAG(
    'youtube_daily',
    default_args=default_args,
    description='🎬 Collecte manuelle YouTube Data API',
    schedule='0 8 * * *',  # Daily 08:00 UTC (10:00 Paris)
    start_date=datetime(2025, 1, 20),
    catchup=False,
    dagrun_timeout=dagrun_timeout_for('youtube_daily'),
    max_active_runs=1,  # serialize external-API collection to protect the daily YouTube quota
    tags=['youtube', 'api', 'production'],
) as dag:

    collect_task = PythonOperator(
        task_id='collect_youtube_data',
        python_callable=collect_youtube_data,
    )
