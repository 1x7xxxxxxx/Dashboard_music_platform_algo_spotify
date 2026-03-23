from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Gestion des chemins
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Import défensif
try:
    from src.collectors.meta_csv_watcher import MetaCSVWatcher
except ImportError as e:
    print(f"❌ ERREUR IMPORT : {e}")
    MetaCSVWatcher = None

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
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
    'on_failure_callback': _on_failure_callback,
}

with DAG(
    'meta_csv_watcher_config',
    default_args=default_args,
    description='Importe le fichier de configuration des campagnes Meta Ads',
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['meta', 'config', 'csv']
) as dag:

    def run_config_watcher(**context):
        import sys
        sys.path.insert(0, '/opt/airflow')
        from src.collectors.meta_csv_watcher import MetaCSVWatcher
        from src.utils.credential_loader import get_active_artists

        conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
        artist_id_conf = conf.get('artist_id')

        artists = get_active_artists(include_artist_id=artist_id_conf)
        if not artists:
            artists = [(1, 'default')]

        for artist_id, artist_name in artists:
            print(f"Meta CSV Watcher — artist_id={artist_id} ({artist_name})")
            watcher = MetaCSVWatcher(artist_id=artist_id)
            watcher.process_files()

    t1 = PythonOperator(
        task_id='process_meta_config_files',
        python_callable=run_config_watcher,
        provide_context=True,
    )