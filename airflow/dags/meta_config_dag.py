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

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
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

    def run_config_watcher():
        if not MetaCSVWatcher:
            raise ImportError("Le module MetaCSVWatcher n'est pas chargé.")
        watcher = MetaCSVWatcher() # ✅ Cela va maintenant marcher car la classe a été renommée
        watcher.process_files()

    t1 = PythonOperator(
        task_id='process_meta_config_files',
        python_callable=run_config_watcher,
    )