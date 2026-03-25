from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path

# 1. Ajout du chemin racine pour trouver les modules src.*
# On remonte de 2 niveaux (src/dags/ -> src/ -> root)
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

# 2. Import du Watcher que nous avons créé
from src.collectors.meta_insight_watcher import MetaAdsWatcher

import logging
logger = logging.getLogger(__name__)


def _on_failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {e}")


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
    'on_failure_callback': _on_failure_callback,
}

# 3. Définition du DAG
with DAG(
    'meta_insights_watcher',  # C'est cet ID qu'Airflow cherchait !
    default_args=default_args,
    description='Surveille et importe les CSV Insights Meta Ads (Age, Pays, etc.)',
    schedule_interval=None,   # Déclenchement manuel via Streamlit
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['meta', 'csv', 'insights']
) as dag:

    def run_watcher_task(**context):
        import sys
        sys.path.insert(0, '/opt/airflow')
        from src.utils.credential_loader import get_active_artists
        from src.collectors.meta_insight_watcher import MetaAdsWatcher
        from src.utils.dag_run_logger import DagRunLogger

        conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
        artist_id_conf = conf.get('artist_id')
        run_id = context.get('run_id', '')

        artists = get_active_artists(include_artist_id=artist_id_conf)
        if not artists:
            artists = [(1, 'default')]

        for artist_id, artist_name in artists:
            logger.info(f"Meta Insights Watcher — artist_id={artist_id} ({artist_name})")
            with DagRunLogger('meta_insights_watcher', artist_id=artist_id,
                              platform='meta', run_id=run_id) as run:
                watcher = MetaAdsWatcher(artist_id=artist_id)
                watcher.process_files()
        logger.info("Meta Insights Watcher — Done.")

    t1 = PythonOperator(
        task_id='process_meta_insights_files',
        python_callable=run_watcher_task,
        provide_context=True,
    )