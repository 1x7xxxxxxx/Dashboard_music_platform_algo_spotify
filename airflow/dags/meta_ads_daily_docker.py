"""DAG Meta Ads pour Docker."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
import logging

# Ajouter le projet au path
sys.path.insert(0, '/opt/airflow')

# Charger .env
from dotenv import load_dotenv
load_dotenv('/opt/airflow/.env')

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=15),
}

def collect_meta_campaigns(**context):
    """Collecte Meta Ads."""
    try:
        from src.collectors.meta_ads_collector import MetaAdsCollector
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('🚀 Collecte Meta Ads...')
        
        # Config Meta depuis .env
        collector = MetaAdsCollector(
            app_id=os.getenv('META_APP_ID'),
            app_secret=os.getenv('META_APP_SECRET'),
            access_token=os.getenv('META_ACCESS_TOKEN'),
            ad_account_id=os.getenv('META_AD_ACCOUNT_ID'),
            api_version=os.getenv('META_API_VERSION', 'v21.0')
        )
        
        campaigns = collector.get_campaigns()
        logger.info(f'✅ {len(campaigns)} campagnes collectées')
        
        # Stocker en DB PostgreSQL
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST'),
            port=int(os.getenv('DATABASE_PORT')),
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        if campaigns:
            count = db.upsert_many(
                table='meta_campaigns',
                data=campaigns,
                conflict_columns=['campaign_id'],
                update_columns=['campaign_name', 'status', 'collected_at']
            )
            logger.info(f'✅ {count} campagnes stockées en base')
        
        db.close()
        return len(campaigns)
        
    except Exception as e:
        logger.error(f'❌ Erreur: {e}')
        import traceback
        traceback.print_exc()
        raise

with DAG(
    'meta_ads_daily_docker',
    default_args=default_args,
    description='Collecte quotidienne Meta Ads (Docker)',
    schedule_interval='0 20 * * *',
    start_date=datetime(2025, 1, 20),
    catchup=False,
    tags=['meta_ads', 'production', 'docker'],
) as dag:
    
    collect_task = PythonOperator(
        task_id='collect_campaigns',
        python_callable=collect_meta_campaigns,
        provide_context=True,
    )
