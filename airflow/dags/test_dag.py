"""DAG de test pour vérifier qu'Airflow fonctionne."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'test_dag',
    default_args=default_args,
    description='DAG de test simple',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['test'],
) as dag:
    
    def print_hello():
        print('✅ Hello from Airflow!')
        print('🎵 Dashboard Music Platform - Airflow is working!')
        return 'success'
    
    hello_task = PythonOperator(
        task_id='print_hello',
        python_callable=print_hello,
    )
    
    hello_task
