"""
DAG Meta Ads CSV Watcher - CONFIGURATION.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from datetime import datetime
import sys
import os
import logging
from pathlib import Path

sys.path.insert(0, '/opt/airflow')
logger = logging.getLogger(__name__)

default_args = {'owner': 'data_team', 'retries': 0}

# Chemins
RAW_DIR = Path('/opt/airflow/data/raw/meta_ads/configuration')
ARCHIVE_DIR = Path('/opt/airflow/data/processed/meta_ads/configuration')

def check_files(**context):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # On cherche .csv et .txt
    files = list(RAW_DIR.glob('*.csv')) + list(RAW_DIR.glob('*.txt'))
    if files:
        context['task_instance'].xcom_push(key='files', value=[str(f) for f in files])
        return 'process_files'
    return 'skip'

def process_files(**context):
    from src.transformers.meta_csv_parser import MetaCSVParser
    from src.database.postgres_handler import PostgresHandler
    
    files = context['task_instance'].xcom_pull(task_ids='check_files', key='files')
    if not files: return

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST'), port=int(os.getenv('DATABASE_PORT')),
        database=os.getenv('DATABASE_NAME'), user=os.getenv('DATABASE_USER'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    
    parser = MetaCSVParser()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    for file_path_str in files:
        file_path = Path(file_path_str)
        logger.info(f"🚀 Traitement : {file_path.name}")
        
        try:
            data = parser.parse(file_path)
            if data:
                # 1. Campagnes
                if not data['campaigns'].empty:
                    cols = list(data['campaigns'].columns)
                    # update_cols = tout sauf la clé primaire
                    up_cols = [c for c in cols if c != 'campaign_id']
                    
                    db.upsert_many('meta_campaigns', data['campaigns'].to_dict('records'), 
                                  ['campaign_id'], up_cols)
                    logger.info(f"✅ {len(data['campaigns'])} campagnes")

                # 2. AdSets
                if not data['adsets'].empty:
                    cols = list(data['adsets'].columns)
                    up_cols = [c for c in cols if c != 'adset_id']
                    
                    db.upsert_many('meta_adsets', data['adsets'].to_dict('records'), 
                                  ['adset_id'], up_cols)
                    logger.info(f"✅ {len(data['adsets'])} adsets")

                # 3. Ads
                if not data['ads'].empty:
                    cols = list(data['ads'].columns)
                    up_cols = [c for c in cols if c != 'ad_id']
                    
                    db.upsert_many('meta_ads', data['ads'].to_dict('records'), 
                                  ['ad_id'], up_cols)
                    logger.info(f"✅ {len(data['ads'])} ads")

            # Archivage
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            target = ARCHIVE_DIR / f"{file_path.stem}_{timestamp}{file_path.suffix}"
            file_path.rename(target)
            logger.info(f"📦 Archivé vers {target.name}")

        except Exception as e:
            logger.error(f"❌ Erreur {file_path.name}: {e}")
            import traceback
            traceback.print_exc()
    
    db.close()

with DAG('meta_csv_watcher_config', default_args=default_args, schedule_interval='*/5 * * * *', 
         start_date=datetime(2025, 1, 1), catchup=False, max_active_runs=1) as dag:
    
    check = BranchPythonOperator(task_id='check_files', python_callable=check_files, provide_context=True)
    process = PythonOperator(task_id='process_files', python_callable=process_files, provide_context=True)
    skip = EmptyOperator(task_id='skip')
    end = EmptyOperator(task_id='end', trigger_rule='none_failed_min_one_success')

    check >> [process, skip]
    process >> end
    skip >> end