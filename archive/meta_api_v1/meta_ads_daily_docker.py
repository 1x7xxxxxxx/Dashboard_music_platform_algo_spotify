"""DAG Meta Ads pour Docker - Collecte Quotidienne Complète."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
import logging

# Ajouter le projet au path
sys.path.insert(0, '/opt/airflow')

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=15),
}

def collect_meta_data(**context):
    """Collecte Campagnes + Adsets + Ads + Insights du jour."""
    try:
        from src.collectors.meta_ads_collector import MetaAdsCollector
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('🚀 Collecte Meta Ads (Daily)...')
        
        # 1. Init Collector
        collector = MetaAdsCollector(
            app_id=os.getenv('META_APP_ID'),
            app_secret=os.getenv('META_APP_SECRET'),
            access_token=os.getenv('META_ACCESS_TOKEN'),
            ad_account_id=os.getenv('META_AD_ACCOUNT_ID'),
            api_version=os.getenv('META_API_VERSION', 'v21.0')
        )
        
        # 2. Init DB
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST'),
            port=int(os.getenv('DATABASE_PORT')),
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD')
        )

        # 3. Structure (Campagnes, Adsets, Ads)
        campaigns = collector.get_campaigns()
        if campaigns:
            db.upsert_many('meta_campaigns', campaigns, ['campaign_id'], 
                          ['campaign_name', 'status', 'objective', 'daily_budget', 'lifetime_budget', 'start_time', 'end_time', 'created_time'])
            logger.info(f'✅ {len(campaigns)} campagnes mises à jour')

        # 4. Insights (Stats) - On récupère les 3 derniers jours pour être sûr
        # (Aujourd'hui, Hier, Avant-hier pour couvrir les délais de reporting Meta)
        insights = collector.get_insights(level='ad', days=3)
        
        if insights:
            # On ne garde que les insights des campagnes qu'on connait (intégrité)
            valid_ids = {c['campaign_id'] for c in campaigns}
            clean_insights = [i for i in insights if i.get('campaign_id') in valid_ids] # Note: get_insights niveau 'ad' retourne ad_id, il faudrait mapper si besoin, mais upsert gère.
            
            # Note: Si get_insights niveau 'ad' retourne 'ad_id', on peut insérer directement
            # L'upsert gère la mise à jour des lignes existantes
            
            count = db.upsert_many('meta_insights', insights, ['ad_id', 'date'], 
                                  ['impressions', 'clicks', 'spend', 'ctr', 'cpc', 'conversions', 'cost_per_conversion'])
            logger.info(f'✅ {count} lignes de stats mises à jour (3 derniers jours)')
        else:
            logger.info('ℹ️ Aucune nouvelle stat trouvée')

        db.close()
        return "Succès"
        
    except Exception as e:
        logger.error(f'❌ Erreur: {e}')
        raise

with DAG(
    'meta_ads_daily_docker',
    default_args=default_args,
    description='Collecte quotidienne Meta Ads (Campagnes + Stats)',
    schedule_interval='0 6 * * *', # Tous les jours à 6h00
    start_date=datetime(2025, 1, 20),
    catchup=False,
    tags=['meta_ads', 'production', 'docker'],
) as dag:
    
    collect_task = PythonOperator(
        task_id='collect_meta_data',
        python_callable=collect_meta_data,
        provide_context=True,
    )