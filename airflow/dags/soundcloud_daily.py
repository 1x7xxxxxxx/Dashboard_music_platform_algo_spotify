from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os

# Ajout du chemin pour trouver vos modules
sys.path.insert(0, '/opt/airflow')

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def run_soundcloud_collector():
    from src.collectors.soundcloud_api_collector import SoundCloudCollector
    collector = SoundCloudCollector()
    collector.run()

with DAG(
    'soundcloud_daily',
    default_args=default_args,
    description='Collecte journalière des stats SoundCloud',
    schedule_interval='0 9 * * *', # Tous les jours à 9h00
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['social', 'soundcloud']
) as dag:

    collect_task = PythonOperator(
        task_id='collect_soundcloud_stats',
        python_callable=run_soundcloud_collector
    )