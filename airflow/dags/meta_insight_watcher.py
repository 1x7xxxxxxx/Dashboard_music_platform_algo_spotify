"""
DAG Meta Ads INSIGHTS Watcher - Version Anti-Doublons (Delete & Insert).
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

RAW_DIR = Path('/opt/airflow/data/raw/meta_ads/insights')
ARCHIVE_DIR = Path('/opt/airflow/data/processed/meta_ads/insights')

def check_files(**context):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = list(RAW_DIR.glob('*.csv')) + list(RAW_DIR.glob('*.txt'))
    if files:
        context['task_instance'].xcom_push(key='files', value=[str(f) for f in files])
        return 'process_files'
    return 'skip'

def process_files(**context):
    from src.transformers.meta_insight_csv_parser import MetaInsightCSVParser
    from src.database.postgres_handler import PostgresHandler
    
    files = context['task_instance'].xcom_pull(task_ids='check_files', key='files')
    if not files: return

    db = PostgresHandler(
        host=os.getenv('DATABASE_HOST'), port=int(os.getenv('DATABASE_PORT')),
        database=os.getenv('DATABASE_NAME'), user=os.getenv('DATABASE_USER'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    
    parser = MetaInsightCSVParser()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    for file_path_str in files:
        file_path = Path(file_path_str)
        try:
            result = parser.parse(file_path)
            
            if result and result['data'] is not None and not result['data'].empty:
                df = result['data']
                table_name = f"meta_insights_{result['type']}"
                
                # --- STRATÉGIE ANTI-DOUBLONS (DELETE & INSERT) ---
                # 1. Identifier les campagnes concernées par ce fichier
                campaigns_in_file = df['campaign_name'].unique().tolist()
                
                if campaigns_in_file:
                    # Echappement des noms pour SQL (sécurité basique)
                    # On utilise des paramètres liés pour la sécurité si possible, 
                    # mais ici on va faire une suppression par lot via execute
                    
                    # On supprime TOUTES les données existantes pour ces campagnes dans cette table
                    # Car le fichier contient tout l'historique à jour pour ces campagnes
                    logger.info(f"🧹 Nettoyage préalable pour {len(campaigns_in_file)} campagnes...")
                    
                    # Construction de la clause IN (...)
                    placeholders = ', '.join(['%s'] * len(campaigns_in_file))
                    delete_query = f"DELETE FROM {table_name} WHERE campaign_name IN ({placeholders})"
                    
                    with db.conn.cursor() as cur:
                        cur.execute(delete_query, tuple(campaigns_in_file))
                        db.conn.commit()
                        logger.info(f"   🗑️ Données précédentes supprimées.")

                # 2. Insertion des nouvelles données
                records = df.to_dict('records')
                db.insert_many(table_name, records)
                logger.info(f"   💾 {len(records)} lignes insérées dans {table_name}")

                # Archivage
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                target = ARCHIVE_DIR / f"{file_path.stem}_{timestamp}{file_path.suffix}"
                file_path.rename(target)
                logger.info(f"📦 Archivé : {target.name}")
            else:
                logger.warning(f"⚠️ Fichier ignoré : {file_path.name}")

        except Exception as e:
            logger.error(f"❌ Erreur {file_path.name}: {e}")
            import traceback
            traceback.print_exc()
            # On ne déplace PAS le fichier en cas d'erreur pour pouvoir le rejouer
    
    db.close()

with DAG('meta_insights_watcher', default_args=default_args, schedule_interval='*/5 * * * *', 
         start_date=datetime(2025, 1, 1), catchup=False, max_active_runs=1) as dag:
    
    check = BranchPythonOperator(task_id='check_files', python_callable=check_files, provide_context=True)
    process = PythonOperator(task_id='process_files', python_callable=process_files, provide_context=True)
    skip = EmptyOperator(task_id='skip')
    end = EmptyOperator(task_id='end', trigger_rule='none_failed_min_one_success')

    check >> [process, skip]
    process >> end
    skip >> end