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
        if creds.get('client_id'):
            os.environ['SOUNDCLOUD_CLIENT_ID'] = creds['client_id']
            logger.info("  Credentials chargés depuis DB")
        else:
            logger.info("  Credentials depuis env vars")

        try:
            collector = SoundCloudCollector(artist_id=artist_id)
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

    collect_task = PythonOperator(
        task_id='collect_soundcloud_stats',
        python_callable=run_soundcloud_collector,
        provide_context=True,
    )
