"""DAG de test pour vérifier qu'Airflow Docker fonctionne."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def test_connection():
    """Test de connexion basique."""
    logger.info('✅ Airflow Docker fonctionne!')
    logger.info('🎵 Dashboard Music Platform - Test OK!')
    return 'success'

with DAG(
    'test_docker',
    default_args=default_args,
    description='DAG de test Docker',
    schedule_interval=None,
    start_date=datetime(2025, 1, 20),
    catchup=False,
    tags=['test', 'docker'],
) as dag:
    
    test_task = PythonOperator(
        task_id='test_connection',
        python_callable=test_connection,
    )
