"""
DAG Apple Music CSV Watcher - Ingestion et Historisation
Fréquence : Toutes les 15 minutes
Description : 
1. Détecte les CSV dans data/raw/apple_music
2. Met à jour la table 'apple_songs_performance' (Dernier état connu)
3. Insère une ligne dans 'apple_songs_history' (Snapshot quotidien pour calculs)
4. Archive le fichier traité
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from datetime import datetime, timedelta, date
import sys
import os
import logging
from pathlib import Path

# Ajouter le chemin pour trouver les modules src
sys.path.insert(0, '/opt/airflow')

logger = logging.getLogger(__name__)


def _on_failure_callback(context):
    try:
        from src.utils.email_alerts import dag_failure_callback
        dag_failure_callback(context)
    except Exception as e:
        logger.error(f"Failure callback error: {e}")


default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'on_failure_callback': _on_failure_callback,
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
            # On transmet la liste des fichiers sous forme de chaînes de caractères
            file_paths = [str(f) for f in csv_files]
            context['task_instance'].xcom_push(key='csv_files', value=file_paths)
            return 'process_csv_files'
        else:
            return 'skip_processing'
        
    except Exception as e:
        logger.error(f'❌ Erreur scan dossier: {e}')
        return 'skip_processing'


def process_csv_files(**context):
    """Traite les CSV : Upsert Performance + Insert History."""
    try:
        # Imports à l'intérieur de la fonction pour éviter les erreurs de Top-Level code
        from src.transformers.apple_music_csv_parser import AppleMusicCSVParser
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('='*70)
        logger.info('🍎 TRAITEMENT CSV APPLE MUSIC')
        logger.info('='*70)
        
        # Récupérer la liste des fichiers
        csv_files = context['task_instance'].xcom_pull(
            task_ids='check_new_csv',
            key='csv_files'
        )
        
        if not csv_files:
            return 0
        
        # Initialiser Parser et DB
        parser = AppleMusicCSVParser()
        
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        # artist_id depuis conf ou défaut 1
        conf = context.get('dag_run').conf or {}
        artist_id = int(conf.get('artist_id', 1))

        processed_count = 0

        for file_path_str in csv_files:
            csv_file = Path(file_path_str)
            if not csv_file.exists():
                continue

            logger.info(f'\n📄 Traitement : {csv_file.name}')

            # 1. Parsing
            result = parser.parse_csv_file(csv_file)
            csv_type = result.get('type')
            data = result.get('data')
            # Injecter artist_id dans chaque ligne
            if data:
                for row in data:
                    row['artist_id'] = artist_id
            
            if not data:
                logger.warning(f"⚠️ Aucune donnée ou type inconnu pour {csv_file.name}")
                continue
            
            # 2. Ingestion selon le type
            try:
                # On se concentre sur le rapport principal "Songs Performance"
                if csv_type == 'songs_performance':
                    
                    # A. UPSERT : Mettre à jour l'état actuel (Performance globale)
                    # Cela sert pour les KPIs "Total à date"
                    count_perf = db.upsert_many(
                        table='apple_songs_performance',
                        data=data,
                        conflict_columns=['artist_id', 'song_name'],
                        update_columns=[
                            'album_name', 'plays', 'listeners',
                            'shazam_count', 'radio_spins', 'purchases',
                            'collected_at'
                        ]
                    )
                    logger.info(f"   ✅ Performance mise à jour : {count_perf} lignes")

                    # B. INSERT : Créer un snapshot pour l'historique (Calculs quotidiens)
                    # On extrait juste ce qui est nécessaire pour le calcul J - (J-1)
                    history_data = []
                    current_date = date.today()
                    timestamp = datetime.now()
                    
                    for row in data:
                        history_data.append({
                            'song_name': row['song_name'],
                            'plays': row['plays'],            # Valeur cumulée à ce jour
                            'shazam_count': row.get('shazam_count', 0),
                            'date': current_date,
                            'collected_at': timestamp
                        })
                    
                    # Nettoyage préventif : Si on relance le script 2 fois le même jour,
                    # on supprime d'abord les entrées d'aujourd'hui pour éviter les doublons
                    for row in history_data:
                        db.execute_query(
                            "DELETE FROM apple_songs_history WHERE song_name = %s AND date = %s",
                            (row['song_name'], row['date'])
                        )
                    
                    # Insertion propre
                    count_hist = db.insert_many('apple_songs_history', history_data)
                    logger.info(f"   ✅ Historique sauvegardé : {count_hist} lignes (Snapshot du jour)")

                else:
                    # Pour les autres types (si jamais tu en remets), on log juste
                    logger.info(f"   ℹ️ Type '{csv_type}' ignoré (focus sur performance/history)")

                # 3. Archivage
                archive_dir = Path('/opt/airflow/data/processed/apple_music')
                archive_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_name = f"{csv_file.stem}_{timestamp_str}{csv_file.suffix}"
                
                csv_file.rename(archive_dir / new_name)
                logger.info(f"   📦 Archivé sous : {new_name}")
                processed_count += 1
                
            except Exception as e:
                logger.error(f"❌ Erreur sur le fichier {csv_file.name}: {e}")
                # On continue vers le fichier suivant même si celui-ci plante
                continue
        
        db.close()
        logger.info(f"🏁 Fin du traitement. {processed_count} fichiers traités.")
        return processed_count

    except Exception as e:
        logger.error(f"❌ Erreur fatale DAG : {e}")
        raise


with DAG(
    dag_id='apple_music_csv_watcher',
    default_args=default_args,
    description='Ingestion Apple Music (Performance + Snapshot Historique)',
    schedule_interval='*/15 * * * *',  # Toutes les 15 minutes
    start_date=datetime(2025, 1, 20),
    catchup=False,
    tags=['apple', 'csv', 'production'],
    max_active_runs=1
) as dag:

    check_task = BranchPythonOperator(
        task_id='check_new_csv',
        python_callable=check_for_new_csv,
        provide_context=True
    )

    process_task = PythonOperator(
        task_id='process_csv_files',
        python_callable=process_csv_files,
        provide_context=True
    )

    skip_task = EmptyOperator(task_id='skip_processing')
    end_task = EmptyOperator(task_id='end', trigger_rule='none_failed_min_one_success')

    # Orchestration
    check_task >> [process_task, skip_task]
    process_task >> end_task
    skip_task >> end_task