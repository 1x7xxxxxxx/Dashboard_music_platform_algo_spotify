from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys

sys.path.insert(0, '/opt/airflow')

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def run_insta_collector():
    from src.collectors.instagram_api_collector import InstagramCollector
    InstagramCollector().run()

with DAG(
    'instagram_daily',
    default_args=default_args,
    description='Collecte journalière Instagram',
    schedule_interval='0 10 * * *', # Tous les jours à 10h
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['social', 'instagram']
) as dag:

    collect_task = PythonOperator(
        task_id='collect_instagram_stats',
        python_callable=run_insta_collector
    )