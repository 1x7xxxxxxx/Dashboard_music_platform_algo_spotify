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

    def run_watcher_task():
        print("🚀 Démarrage du Meta Ads Insight Watcher...")
        watcher = MetaAdsWatcher()
        watcher.process_files()
        print("✅ Fin du traitement.")

    t1 = PythonOperator(
        task_id='process_meta_insights_files',
        python_callable=run_watcher_task,
    )   