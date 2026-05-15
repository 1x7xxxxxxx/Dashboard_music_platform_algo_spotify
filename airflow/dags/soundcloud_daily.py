"""DAG SoundCloud — collecte journalière des stats.

Brick 6 : supporte artist_id dans dag_run.conf.
  - conf.artist_id fourni → collecte pour cet artiste uniquement (credentials depuis DB).
  - conf absent           → fallback sur env vars (comportement historique, artist_id=1).
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, '/opt/airflow')

import logging
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
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'on_failure_callback': _on_failure_callback,
}


def precheck_soundcloud_credentials(**context):
    """Fail fast if client_id, client_secret or user_id is missing for any active artist."""
    from src.utils.credential_loader import get_active_artists, load_platform_credentials

    artists = get_active_artists()
    if not artists:
        logger.info("No active artists — skipping credential pre-check.")
        return

    missing = []
    for aid, name in artists:
        creds = load_platform_credentials(aid, 'soundcloud')
        absent = [k for k in ('client_id', 'client_secret', 'user_id') if not creds.get(k)]
        if absent:
            missing.append(f"{name} (id={aid}) — champs manquants : {', '.join(absent)}")

    if missing:
        raise ValueError(
            f"Credentials SoundCloud incomplets pour : {'; '.join(missing)}. "
            "Action : Dashboard → Credentials → SoundCloud → saisir client_id, "
            "client_secret et user_id (app créée sur soundcloud.com/you/apps)."
        )
    logger.info(f"✅ Credentials SoundCloud OK pour {len(artists)} artiste(s)")


def run_soundcloud_collector(**context):
    import logging
    from src.collectors.soundcloud_api_collector import SoundCloudCollector
    from src.utils.credential_loader import load_platform_credentials, get_active_artists

    logger = logging.getLogger(__name__)

    # ── Résolution de l'artiste ────────────────────────────────────────
    conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
    artist_id_conf = conf.get('artist_id')

    artists = get_active_artists(include_artist_id=artist_id_conf)

    if not artists:
        # Fallback : env vars, artist_id=1
        logger.info("Aucun artiste en DB — fallback env vars (artist_id=1)")
        artists = [(1, 'default')]

    for artist_id, artist_name in artists:
        logger.info(f"▶ SoundCloud collect — artist_id={artist_id} ({artist_name})")

        # ── Credentials depuis DB, fallback env vars ───────────────────
        creds = load_platform_credentials(artist_id, 'soundcloud')
        client_id     = creds.get('client_id')     or os.getenv('SOUNDCLOUD_CLIENT_ID')
        client_secret = creds.get('client_secret') or os.getenv('SOUNDCLOUD_CLIENT_SECRET')
        user_id       = creds.get('user_id')       or os.getenv('SOUNDCLOUD_USER_ID')
        refresh_token = creds.get('refresh_token') or os.getenv('SOUNDCLOUD_REFRESH_TOKEN')
        logger.info("  credentials chargés (DB + env vars fallback)")

        try:
            collector = SoundCloudCollector(
                artist_id=artist_id,
                client_id=client_id,
                client_secret=client_secret,
                user_id=user_id,
                refresh_token=refresh_token,
            )
            collector.run()
            logger.info(f"  ✅ Collecte terminée pour {artist_name}")
        except Exception as e:
            logger.error(f"  ❌ Erreur pour {artist_name} : {e}")
            raise


with DAG(
    'soundcloud_daily',
    default_args=default_args,
    description='Collecte journalière des stats SoundCloud',
    schedule_interval='0 9 * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['social', 'soundcloud'],
) as dag:

    precheck_task = PythonOperator(
        task_id='precheck_credentials',
        python_callable=precheck_soundcloud_credentials,
    )

    collect_task = PythonOperator(
        task_id='collect_soundcloud_stats',
        python_callable=run_soundcloud_collector,
    )

    precheck_task >> collect_task
