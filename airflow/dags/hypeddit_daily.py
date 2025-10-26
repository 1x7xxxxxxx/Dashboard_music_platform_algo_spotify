"""
DAG Hypeddit - Collecte quotidienne
Fréquence : Quotidienne à 08h00
Description : Collecte les campagnes Hypeddit et leurs statistiques
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
import logging

# Ajouter le projet au path Python
sys.path.insert(0, '/opt/airflow')

# Charger les variables d'environnement
from dotenv import load_dotenv
load_dotenv('/opt/airflow/.env')

logger = logging.getLogger(__name__)

# Configuration par défaut du DAG
default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
}


def collect_hypeddit_campaigns(**context):
    """Collecte les campagnes Hypeddit."""
    try:
        from src.collectors.hypeddit_collector import HypedditCollector
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('='*70)
        logger.info('🚀 COLLECTE HYPEDDIT - CAMPAGNES')
        logger.info('='*70)
        
        # Initialiser le collector
        collector = HypedditCollector(
            api_key=os.getenv('HYPEDDIT_API_KEY')
        )
        
        # Récupérer les campagnes
        campaigns = collector.get_campaigns()
        
        if not campaigns:
            logger.warning('⚠️ Aucune campagne récupérée')
            return 0
        
        logger.info(f'✅ {len(campaigns)} campagne(s) récupérée(s)')
        
        # Stocker en base PostgreSQL
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        # Upsert des campagnes
        count = db.upsert_many(
            table='hypeddit_campaigns',
            data=campaigns,
            conflict_columns=['campaign_id'],
            update_columns=[
                'campaign_name', 'campaign_type', 'status', 
                'budget', 'target_url', 'collected_at'
            ]
        )
        
        logger.info(f'✅ {count} campagne(s) stockée(s) en base')
        
        db.close()
        
        logger.info('='*70 + '\n')
        
        # Pousser le nombre de campagnes dans XCom pour la tâche suivante
        context['task_instance'].xcom_push(
            key='campaigns_count',
            value=len(campaigns)
        )
        
        # Pousser les IDs des campagnes
        campaign_ids = [c['campaign_id'] for c in campaigns]
        context['task_instance'].xcom_push(
            key='campaign_ids',
            value=campaign_ids
        )
        
        return len(campaigns)
        
    except Exception as e:
        logger.error(f'❌ Erreur collecte campagnes Hypeddit: {e}')
        import traceback
        logger.error(traceback.format_exc())
        raise


def collect_hypeddit_stats(**context):
    """Collecte les statistiques quotidiennes des campagnes Hypeddit."""
    try:
        from src.collectors.hypeddit_collector import HypedditCollector
        from src.database.postgres_handler import PostgresHandler
        from datetime import datetime, timedelta
        
        logger.info('='*70)
        logger.info('📊 COLLECTE HYPEDDIT - STATISTIQUES')
        logger.info('='*70)
        
        # Récupérer les IDs des campagnes depuis XCom
        campaign_ids = context['task_instance'].xcom_pull(
            task_ids='collect_campaigns',
            key='campaign_ids'
        )
        
        if not campaign_ids:
            logger.warning('⚠️ Aucune campagne à traiter')
            return 0
        
        logger.info(f'📋 {len(campaign_ids)} campagne(s) à traiter')
        
        # Initialiser le collector
        collector = HypedditCollector(
            api_key=os.getenv('HYPEDDIT_API_KEY')
        )
        
        # Connexion DB
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        # Collecter les stats des 30 derniers jours pour chaque campagne
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        total_stats = 0
        
        for i, campaign_id in enumerate(campaign_ids, 1):
            logger.info(f'\n[{i}/{len(campaign_ids)}] Campagne: {campaign_id}')
            
            # Récupérer les stats quotidiennes
            daily_stats = collector.get_campaign_daily_breakdown(
                campaign_id,
                start_date_str,
                end_date_str
            )
            
            if daily_stats:
                # Stocker en DB
                count = db.upsert_many(
                    table='hypeddit_daily_stats',
                    data=daily_stats,
                    conflict_columns=['campaign_id', 'date'],
                    update_columns=[
                        'impressions', 'clicks', 'conversions', 'downloads',
                        'streams', 'follows', 'pre_saves', 'spend', 'ctr',
                        'conversion_rate', 'cost_per_conversion', 'collected_at'
                    ]
                )
                
                total_stats += len(daily_stats)
                logger.info(f'   ✅ {count} jour(s) de stats stocké(s)')
            else:
                logger.warning(f'   ⚠️ Aucune stat pour cette campagne')
        
        db.close()
        
        logger.info('\n' + '='*70)
        logger.info(f'✅ TOTAL: {total_stats} enregistrement(s) de stats')
        logger.info('='*70 + '\n')
        
        return total_stats
        
    except Exception as e:
        logger.error(f'❌ Erreur collecte stats Hypeddit: {e}')
        import traceback
        logger.error(traceback.format_exc())
        raise


# Définition du DAG
with DAG(
    dag_id='hypeddit_daily',
    default_args=default_args,
    description='🎵 Collecte quotidienne Hypeddit (campagnes + stats)',
    schedule_interval=None,  # Quotidien à 08h00
    start_date=datetime(2025, 1, 27),
    catchup=False,  # Ne pas rattraper les exécutions passées
    tags=['hypeddit', 'production', 'marketing'],
    max_active_runs=1,  # Une seule exécution à la fois
) as dag:
    
    # Tâche 1: Collecter les campagnes
    collect_campaigns_task = PythonOperator(
        task_id='collect_campaigns',
        python_callable=collect_hypeddit_campaigns,
        provide_context=True,
    )
    
    # Tâche 2: Collecter les statistiques
    collect_stats_task = PythonOperator(
        task_id='collect_stats',
        python_callable=collect_hypeddit_stats,
        provide_context=True,
    )
    
    # Définir l'ordre d'exécution
    collect_campaigns_task >> collect_stats_task