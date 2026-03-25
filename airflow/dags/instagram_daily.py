from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys

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
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'on_failure_callback': _on_failure_callback,
}

def precheck_instagram_credentials(**context):
    """Fail fast if no Meta/Instagram credentials exist for any active artist."""
    from src.utils.credential_loader import get_active_artists, load_platform_credentials

    artists = get_active_artists()
    if not artists:
        logger.info("No active artists — skipping credential pre-check.")
        return

    missing = [
        f"{name} (id={aid})"
        for aid, name in artists
        if not load_platform_credentials(aid, 'meta').get('access_token')
    ]
    if missing:
        raise ValueError(
            f"Credentials Meta/Instagram manquants pour : {', '.join(missing)}. "
            "Action : developers.facebook.com → Graph API Explorer → "
            "renouveler le Long-lived token (scopes: instagram_basic, instagram_manage_insights)."
        )
    logger.info(f"✅ Credentials Meta/Instagram OK pour {len(artists)} artiste(s)")


def run_insta_collector(**context):
    import os
    import logging
    from src.collectors.instagram_api_collector import InstagramCollector
    from src.utils.credential_loader import load_platform_credentials, get_active_artists

    logger = logging.getLogger(__name__)

    conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
    artist_id_conf = conf.get('artist_id')

    artists = get_active_artists(include_artist_id=artist_id_conf)
    if not artists:
        logger.info("No active artists in DB — fallback env vars (artist_id=1)")
        artists = [(1, 'default')]

    for artist_id, artist_name in artists:
        logger.info(f"Instagram collect — artist_id={artist_id} ({artist_name})")

        creds = load_platform_credentials(artist_id, 'meta')
        if creds.get('access_token'):
            os.environ['INSTAGRAM_ACCESS_TOKEN'] = creds['access_token']
            logger.info("  access_token loaded from DB")
        if creds.get('ig_user_id'):
            os.environ['INSTAGRAM_USER_ID'] = creds['ig_user_id']
            logger.info("  ig_user_id loaded from DB")

        try:
            InstagramCollector(artist_id=artist_id).run()
            logger.info(f"  Collect done for {artist_name}")
        except Exception as e:
            logger.error(f"  Error for {artist_name}: {e}")
            raise

with DAG(
    'instagram_daily',
    default_args=default_args,
    description='Collecte journalière Instagram',
    schedule_interval='0 10 * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['social', 'instagram']
) as dag:

    precheck_task = PythonOperator(
        task_id='precheck_credentials',
        python_callable=precheck_instagram_credentials,
    )

    collect_task = PythonOperator(
        task_id='collect_instagram_stats',
        provide_context=True,
        python_callable=run_insta_collector
    )

    precheck_task >> collect_task