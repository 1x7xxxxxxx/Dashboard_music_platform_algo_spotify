"""
DAG Spotify for Artists - Surveillance automatique des CSV
Fréquence : Toutes les 15 minutes
Description : Détecte et traite automatiquement les nouveaux CSV S4A
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from datetime import datetime, timedelta
import sys
import os
import logging
from pathlib import Path

# Ajouter le projet au path Python
sys.path.insert(0, '/opt/airflow')

#Déjà lecture via docker-compose.yml
#from dotenv import load_dotenv
#load_dotenv('/opt/airflow/.env')

logger = logging.getLogger(__name__)

# Configuration par défaut du DAG
default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def check_for_new_csv(**context):
    """
    Vérifie s'il y a de nouveaux CSV à traiter dans le dossier raw.
    
    Returns:
        str: 'process_csv' si fichiers trouvés, 'skip_processing' sinon
    """
    try:
        # Dossier où les CSV sont déposés
        raw_dir = Path('/opt/airflow/data/raw/spotify_for_artists')
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Chercher tous les fichiers .csv
        csv_files = list(raw_dir.glob('*.csv'))
        
        logger.info(f'📁 Scan du dossier: {raw_dir}')
        logger.info(f'📊 {len(csv_files)} fichier(s) CSV trouvé(s)')
        
        if csv_files:
            # Afficher la liste des fichiers
            for csv_file in csv_files:
                logger.info(f'   📄 {csv_file.name}')
            
            # Pousser la liste des fichiers dans XCom pour la tâche suivante
            file_paths = [str(f) for f in csv_files]
            context['task_instance'].xcom_push(
                key='csv_files',
                value=file_paths
            )
            
            # Indiquer qu'il faut traiter les fichiers
            return 'process_csv_files'
        else:
            logger.info('ℹ️  Aucun nouveau CSV à traiter')
            # Passer à la tâche de fin sans traitement
            return 'skip_processing'
        
    except Exception as e:
        logger.error(f'❌ Erreur lors de la vérification des CSV: {e}')
        import traceback
        logger.error(traceback.format_exc())
        return 'skip_processing'


def process_csv_files(**context):
    """
    Traite tous les CSV trouvés : parse + stocke en DB + archive.
    """
    try:
        from src.transformers.s4a_csv_parser import S4ACSVParser
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('='*70)
        logger.info('🔄 TRAITEMENT DES CSV SPOTIFY FOR ARTISTS')
        logger.info('='*70)
        
        # Récupérer la liste des fichiers depuis XCom
        csv_files = context['task_instance'].xcom_pull(
            task_ids='check_new_csv',
            key='csv_files'
        )
        
        if not csv_files:
            logger.warning('⚠️  Aucun fichier CSV dans XCom')
            return 0
        
        # Initialiser le parser
        parser = S4ACSVParser()
        
        # Connexion à PostgreSQL
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        processed_count = 0
        total_records = 0
        
        # Traiter chaque fichier CSV
        for csv_file_str in csv_files:
            csv_file = Path(csv_file_str)
            
            if not csv_file.exists():
                logger.warning(f'⚠️  Fichier introuvable: {csv_file.name}')
                continue
            
            logger.info(f'\n📄 Traitement: {csv_file.name}')
            
            # Parser le CSV
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
            
            # Stocker dans PostgreSQL selon le type
            try:
                if csv_type == 'songs_global':
                    count = db.upsert_many(
                        table='s4a_songs_global',
                        data=data,
                        conflict_columns=['song'],
                        update_columns=['listeners', 'streams', 'saves', 'release_date', 'collected_at']
                    )
                    logger.info(f'   ✅ {count} chanson(s) stockée(s)')
                
                elif csv_type == 'song_timeline':
                    count = db.upsert_many(
                        table='s4a_song_timeline',
                        data=data,
                        conflict_columns=['song', 'date'],
                        update_columns=['streams', 'collected_at']
                    )
                    logger.info(f'   ✅ {count} enregistrement(s) timeline stocké(s)')
                
                elif csv_type == 'audience':
                    count = db.upsert_many(
                        table='s4a_audience',
                        data=data,
                        conflict_columns=['date'],
                        update_columns=['listeners', 'streams', 'followers', 'collected_at']
                    )
                    logger.info(f'   ✅ {count} jour(s) d\'audience stocké(s)')
                
                else:
                    logger.error(f'   ❌ Type non supporté: {csv_type}')
                    continue
                
                total_records += len(data)
                
                # Archiver le fichier traité avec succès
                archive_dir = Path('/opt/airflow/data/processed/spotify_for_artists')
                archive_dir.mkdir(parents=True, exist_ok=True)
                
                # Nom du fichier archivé avec timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_name = f"{csv_file.stem}_{timestamp}{csv_file.suffix}"
                archive_path = archive_dir / new_name
                
                # Déplacer le fichier
                csv_file.rename(archive_path)
                logger.info(f'   📦 Archivé: {archive_path.name}')
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f'   ❌ Erreur stockage: {e}')
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        # Fermer la connexion DB
        db.close()
        
        # Résumé final
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


# Définition du DAG
with DAG(
    dag_id='s4a_csv_watcher',
    default_args=default_args,
    description='🎵 Surveillance automatique des CSV Spotify for Artists',
    schedule_interval=None,  # manuellement
    start_date=datetime(2025, 1, 20),
    catchup=False,  # Ne pas rattraper les exécutions passées
    tags=['spotify', 's4a', 'csv', 'production'],
    max_active_runs=1,  # Une seule exécution à la fois
) as dag:
    
    # Tâche 1: Vérifier s'il y a de nouveaux CSV (avec branchement)
    check_csv_task = BranchPythonOperator(
        task_id='check_new_csv',
        python_callable=check_for_new_csv,
        provide_context=True,
    )
    
    # Tâche 2: Traiter les CSV trouvés
    process_csv_task = PythonOperator(
        task_id='process_csv_files',
        python_callable=process_csv_files,
        provide_context=True,
    )
    
    # Tâche 3: Fin (si pas de fichiers à traiter)
    skip_task = EmptyOperator(
        task_id='skip_processing'
    )
    
    # Tâche 4: Fin (après traitement)
    end_task = EmptyOperator(
        task_id='end',
        trigger_rule='none_failed_min_one_success'  # Continue si au moins une branche réussit
    )
    
    # Définir le flux d'exécution
    # Le check_csv_task décide quelle branche prendre
    check_csv_task >> [process_csv_task, skip_task]
    process_csv_task >> end_task
    skip_task >> end_task