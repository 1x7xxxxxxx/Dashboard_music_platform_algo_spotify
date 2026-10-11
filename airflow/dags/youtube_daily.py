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
import time as _time
from src.utils.dag_timeouts import dagrun_timeout_for

sys.path.insert(0, '/opt/airflow')
from src.utils.dag_callbacks import on_failure  # noqa: E402 — R265, the ONE callback

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
    'on_failure_callback': on_failure,
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

        db = PostgresHandler.from_env_or_config()

        results = []
        artists_with_creds = 0
        successful_fetches = 0
        unreadable: list[Exception] = []   # magasin illisible : ni « connecté » ni « pas connecté »
        per_artist_errors = []  # multi-tenant isolation: one bad tenant must not abort the fleet

        for saas_artist_id, artist_name in artists:
            logger.info(f'YouTube collect — artist_id={saas_artist_id} ({artist_name})')

            # DANS l'isolement : cette lecture LÈVE sur un magasin illisible, et
            # elle était au-dessus du `try` qui commence 26 lignes plus bas — donc un
            # seul locataire illisible avortait la collecte des suivants.
            try:
                creds = load_platform_credentials(saas_artist_id, 'youtube')
            except Exception as e:                   # noqa: BLE001 — isolement par locataire
                logger.error(f'  Credentials unreadable for artist_id={saas_artist_id} '
                             f'({artist_name}): {safe_error(e)}')
                per_artist_errors.append((saas_artist_id, artist_name,
                                          safe_error(e, limit=200)))
                # ⚠️ RETENU, pas seulement journalisé : `continue` arrive AVANT le
                # compteur de locataires configurés, donc sans cette liste un magasin
                # en panne pour TOUT le monde se lirait comme « aucun artiste
                # connecté ». Classe `une-erreur-avalée-devient-une-absence`.
                unreadable.append(e)
                continue
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
                # LE CHRONOMÈTRE. `record_tenant_success` écrivait `started_at == ended_at`,
                # donc une durée de zéro : quatre DAGs sur cinq étaient dans ce cas, et toute
                # moyenne calculée sur `etl_run_log` intégrait des zéros qui n'étaient pas des
                # mesures. Le schéma impose `started_at NOT NULL` — on ne peut donc pas dire
                # « je ne sais pas » ; on mesure.
                _t0 = _time.monotonic()
                collector = YouTubeCollector(api_key)
                # 200 (not 50): older releases (e.g. a remix) get pushed past the 50 most-recent
                # uploads by frequent content (DJ sets) and were never collected → unmappable.
                # DEUX chaînes, pas une. Mesuré le 2026-09-05 : un artiste
                # distribué en a une principale (ses uploads) et une « … - Topic »
                # auto-générée par YouTube (ses titres distribués), et elles portent
                # des données différentes — FJAAK : 53 vidéos / 11 M vues d'un côté,
                # 172 vidéos / 880 k vues de l'autre. Aucune ne remplace l'autre.
                # La clé de conflit est (artist_id, channel_id) depuis la migration
                # 064 : deux chaînes pour un locataire tiennent déjà en base.
                _channels = [channel_id]
                _topic = (creds.get('topic_channel_id') or '').strip()
                if _topic and _topic != channel_id:
                    _channels.append(_topic)
                _videos_total = 0
                for channel_id_being_collected in _channels:
                    data = collector.collect_all_data(channel_id=channel_id_being_collected, max_videos=200, collect_comments=False)

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
                            # (artist_id, comment_id) depuis la migration 100 :
                            # l'index unique est désormais par locataire, et un
                            # ON CONFLICT dont la cible n'a plus d'index
                            # correspondant LÈVE (leçon de la migration 095).
                            conflict_columns=['artist_id', 'comment_id'],
                            update_columns=['like_count', 'collected_at']
                        )

                    _videos_total += len(data['videos'])

                record_tenant_success('youtube_daily', saas_artist_id, 'youtube',
                                      _videos_total, run_id,
                                      duration_ms=int((_time.monotonic() - _t0) * 1000))
                results.append({'artist': artist_name, 'videos': _videos_total,
                                'channels': len(_channels)})
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
        if successful_fetches == 0 and unreadable:
            raise unreadable[0]
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


_REAUTHORIZE = 'tools/dev/youtube_analytics_authorize.py (runbook « YouTube Analytics »)'


def persist_analytics(db, artist_id: int, data: dict) -> int:
    """Upsert the three Analytics reports for ONE tenant; returns the row count.

    Literal table names on purpose: the export and ON CONFLICT guards read them.
    artist_id is in every conflict target and in no update list — a row never changes owner.
    """
    from datetime import datetime, timezone
    stamp = {'artist_id': artist_id, 'collected_at': datetime.now(timezone.utc)}
    window = {'window_end': data['window_end'], 'window_days': data['window_days']}
    measures = ['views', 'minutes_watched', 'subscribers_gained', 'subscribers_lost',
                'collected_at']
    videos = [{**r, **stamp, **window} for r in data['videos']]
    daily = [{**r, **stamp} for r in data['daily']]
    traffic = [{**r, **stamp} for r in data['traffic']]
    if videos:
        db.upsert_many('youtube_analytics_video_window', videos,
                       conflict_columns=['artist_id', 'video_id', 'window_end', 'window_days'],
                       update_columns=measures)
    if daily:
        db.upsert_many('youtube_analytics_channel_daily', daily,
                       conflict_columns=['artist_id', 'day'], update_columns=measures)
    if traffic:
        db.upsert_many('youtube_analytics_traffic_daily', traffic,
                       conflict_columns=['artist_id', 'day', 'source_type'],
                       update_columns=['views', 'minutes_watched', 'collected_at'])
    rows = len(videos) + len(daily) + len(traffic)
    return rows


def _forget_expired_token(artist_id: int) -> None:
    """Drop the refused token so later nights SKIP (naming the gesture), not fail again."""
    from datetime import datetime, timezone
    from src.utils.credential_loader import save_platform_credentials, update_platform_secret
    update_platform_secret(artist_id, 'youtube_analytics', 'refresh_token', '')
    save_platform_credentials(artist_id, 'youtube_analytics', {
        'expired_at': datetime.now(timezone.utc).isoformat(timespec='milliseconds')})


def _analytics_skip_reason(creds: dict) -> str:
    if creds.get('expired_at'):
        return f"YouTube Analytics authorization expired — re-authorize: {_REAUTHORIZE}"
    return f"YouTube Analytics not authorized — {_REAUTHORIZE}"


def _analytics_one(db, aid: int, run_id: str, app: tuple) -> bool:
    """One tenant: True when collected, False when skipped; raises on failure."""
    from datetime import date
    from src.collectors.youtube_analytics_collector import YouTubeAnalyticsCollector
    from src.utils.credential_loader import load_platform_credentials
    from src.utils.dag_run_logger import record_tenant_skip, record_tenant_success
    creds = load_platform_credentials(aid, 'youtube_analytics')
    token = (creds.get('refresh_token') or '').strip()
    if not token:
        record_tenant_skip('youtube_daily', aid, 'youtube_analytics',
                           _analytics_skip_reason(creds), run_id)
        return False
    if not all(app):
        raise RuntimeError('GOOGLE_OAUTH_CLIENT_ID / _SECRET absent from the Airflow '
                           'environment — admin action (docker-compose env map)')
    t0 = _time.monotonic()
    data = YouTubeAnalyticsCollector(*app, token).collect(date.today())
    rows = persist_analytics(db, aid, data)
    record_tenant_success('youtube_daily', aid, 'youtube_analytics', rows, run_id,
                          duration_ms=int((_time.monotonic() - t0) * 1000))
    return True


def collect_youtube_analytics(**context):
    """R511 — subscribers per video, watch time, traffic sources, for AUTHORIZED tenants.

    A tenant without a token is skipped with the gesture named. An expired token is ONE
    failure, then forgotten — so the alert fires once, not every night.
    """
    from src.collectors.youtube_analytics_collector import AnalyticsAuthorizationExpired
    from src.database.postgres_handler import PostgresHandler
    from src.utils.credential_loader import get_active_artists
    from src.utils.dag_run_logger import record_tenant_failure
    from src.utils.safe_error import safe_error

    conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
    run_id = context.get('run_id', '')
    app = (os.getenv('GOOGLE_OAUTH_CLIENT_ID', '').strip(),
           os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '').strip())
    artists = get_active_artists(include_artist_id=conf.get('artist_id'))
    if not artists:
        return
    db = PostgresHandler.from_env_or_config()
    attempted, failed, failures = 0, 0, []
    try:
        for aid, name in artists:
            try:
                attempted += _analytics_one(db, aid, run_id, app)
            except Exception as e:  # noqa: BLE001 — per-tenant isolation
                attempted += 1
                failed += 1
                failures.append(f'{aid}/{name}: {safe_error(e, limit=200)}')
                record_tenant_failure('youtube_daily', aid, 'youtube_analytics', e, run_id)
                if isinstance(e, AnalyticsAuthorizationExpired):
                    try:
                        _forget_expired_token(aid)
                    except Exception as forget:  # noqa: BLE001 — next night fails again, visibly
                        failures.append(f'{aid}/{name}: token not forgotten — '
                                        f'{safe_error(forget, limit=200)}')
    finally:
        db.close()
    if failed and failed == attempted:
        raise RuntimeError('YouTube Analytics failed for every authorized tenant: '
                           + '; '.join(failures))


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

    # After the Data API task (one quota at a time), and whatever it did: an Analytics
    # tenant must not lose its night because another tenant's public read failed.
    analytics_task = PythonOperator(
        task_id='collect_youtube_analytics',
        python_callable=collect_youtube_analytics,
        trigger_rule='all_done',
    )
    collect_task >> analytics_task
