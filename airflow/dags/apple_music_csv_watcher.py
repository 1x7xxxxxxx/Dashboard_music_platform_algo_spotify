"""
DAG Apple Music CSV Watcher - Surveillance automatique des CSV - VERSION CORRIGÉE
Fréquence : Toutes les 15 minutes
Description : Détecte et traite automatiquement les nouveaux CSV Apple Music
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from datetime import datetime, timedelta
import sys
import os
import logging
from pathlib import Path

sys.path.insert(0, '/opt/airflow')

#Déjà lecture via docker-compose.yml
#from dotenv import load_dotenv
#load_dotenv('/opt/airflow/.env')

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def check_for_new_csv(**context):
    """Vérifie s'il y a de nouveaux CSV à traiter."""
    try:
        raw_dir = Path('/opt/airflow/data/raw/apple_music')
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        csv_files = list(raw_dir.glob('*.csv'))
        
        logger.info(f'📁 Scan du dossier: {raw_dir}')
        logger.info(f'📊 {len(csv_files)} fichier(s) CSV trouvé(s)')
        
        if csv_files:
            for csv_file in csv_files:
                logger.info(f'   📄 {csv_file.name}')
            
            file_paths = [str(f) for f in csv_files]
            context['task_instance'].xcom_push(
                key='csv_files',
                value=file_paths
            )
            
            return 'process_csv_files'
        else:
            logger.info('ℹ️  Aucun nouveau CSV à traiter')
            return 'skip_processing'
        
    except Exception as e:
        logger.error(f'❌ Erreur lors de la vérification des CSV: {e}')
        import traceback
        logger.error(traceback.format_exc())
        return 'skip_processing'


def process_csv_files(**context):
    """Traite tous les CSV trouvés."""
    try:
        from src.transformers.apple_music_csv_parser import AppleMusicCSVParser
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('='*70)
        logger.info('🍎 TRAITEMENT DES CSV APPLE MUSIC')
        logger.info('='*70)
        
        csv_files = context['task_instance'].xcom_pull(
            task_ids='check_new_csv',
            key='csv_files'
        )
        
        if not csv_files:
            logger.warning('⚠️  Aucun fichier CSV dans XCom')
            return 0
        
        parser = AppleMusicCSVParser()
        
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        processed_count = 0
        total_records = 0
        
        for csv_file_str in csv_files:
            csv_file = Path(csv_file_str)
            
            if not csv_file.exists():
                logger.warning(f'⚠️  Fichier introuvable: {csv_file.name}')
                continue
            
            logger.info(f'\n📄 Traitement: {csv_file.name}')
            
            result = parser.parse_csv_file(csv_file)
            
            if not result['type']:
                logger.warning(f'⚠️  Type CSV non reconnu: {csv_file.name}')
                continue
            
            if not result['data']:
                logger.warning(f'⚠️  Aucune donnée extraite: {csv_file.name}')
                continue
            
            csv_type = result['type']
            data = result['data']
            
            logger.info(f'   🏷️  Type: {csv_type}')
            logger.info(f'   📊 Enregistrements: {len(data)}')
            
            try:
                if csv_type == 'songs_performance':
                    # ✅ CORRECTION : Ajouter les nouvelles colonnes dans update_columns
                    count = db.upsert_many(
                        table='apple_songs_performance',
                        data=data,
                        conflict_columns=['song_name'],
                        update_columns=[
                            'album_name', 'plays', 'listeners',
                            'shazam_count', 'radio_spins', 'purchases',
                            'collected_at'
                        ]
                    )
                    logger.info(f'   ✅ {count} chanson(s) stockée(s)')
                
                elif csv_type == 'daily_plays':
                    count = db.upsert_many(
                        table='apple_daily_plays',
                        data=data,
                        conflict_columns=['song_name', 'date'],
                        update_columns=['plays', 'collected_at']
                    )
                    logger.info(f'   ✅ {count} enregistrement(s) stocké(s)')
                
                elif csv_type == 'listeners':
                    count = db.upsert_many(
                        table='apple_listeners',
                        data=data,
                        conflict_columns=['date'],
                        update_columns=['listeners', 'collected_at']
                    )
                    logger.info(f'   ✅ {count} jour(s) stocké(s)')
                
                else:
                    logger.error(f'   ❌ Type non supporté: {csv_type}')
                    continue
                
                total_records += len(data)
                
                # Archiver
                archive_dir = Path('/opt/airflow/data/processed/apple_music')
                archive_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_name = f"{csv_file.stem}_{timestamp}{csv_file.suffix}"
                archive_path = archive_dir / new_name
                
                csv_file.rename(archive_path)
                logger.info(f'   📦 Archivé: {archive_path.name}')
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f'   ❌ Erreur stockage: {e}')
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        db.close()
        
        logger.info('\n' + '='*70)
        logger.info(f'✅ TRAITEMENT TERMINÉ')
        logger.info('='*70)
        logger.info(f'📊 Fichiers traités: {processed_count}/{len(csv_files)}')
        logger.info(f'📊 Enregistrements stockés: {total_records}')
        logger.info('='*70)
        
        return processed_count
        
    except Exception as e:
        logger.error(f'❌ Erreur globale traitement CSV: {e}')
        import traceback
        logger.error(traceback.format_exc())
        raise


with DAG(
    dag_id='apple_music_csv_watcher',
    default_args=default_args,
    description='🍎 Surveillance automatique des CSV Apple Music',
    schedule_interval='*/15 * * * *',  # Toutes les 15 minutes
    start_date=datetime(2025, 1, 20),
    catchup=False,
    tags=['apple_music', 'csv', 'production'],
    max_active_runs=1,
) as dag:
    
    check_csv_task = BranchPythonOperator(
        task_id='check_new_csv',
        python_callable=check_for_new_csv,
        provide_context=True,
    )
    
    process_csv_task = PythonOperator(
        task_id='process_csv_files',
        python_callable=process_csv_files,
        provide_context=True,
    )
    
    skip_task = EmptyOperator(
        task_id='skip_processing'
    )
    
    end_task = EmptyOperator(
        task_id='end',
        trigger_rule='none_failed_min_one_success'
    )
    
    check_csv_task >> [process_csv_task, skip_task]
    process_csv_task >> end_task
    skip_task >> end_task