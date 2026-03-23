"""DAG Spotify API - Collecte quotidienne artistes et tracks.

Brick 6 : supporte artist_id dans dag_run.conf.
  - conf.artist_id fourni → credentials depuis DB pour cet artiste.
  - conf absent           → fallback sur env vars (comportement historique).
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, date  # ✅ AJOUT de 'date'
import sys
import os
import logging

# Ajouter le projet au path
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
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'on_failure_callback': _on_failure_callback,
}


def collect_spotify_artists(**context):
    """Collecte les statistiques des artistes via API Spotify."""
    
    try:
        from src.collectors.spotify_api import SpotifyCollector
        from src.database.postgres_handler import PostgresHandler
        from src.utils.credential_loader import load_platform_credentials

        logger.info('🎸 Collecte Spotify - Artistes...')

        from src.utils.credential_loader import get_active_artists

        conf = (context.get('dag_run').conf or {}) if context.get('dag_run') else {}
        artist_id_conf = conf.get('artist_id')

        active_artists = get_active_artists(include_artist_id=artist_id_conf)
        if not active_artists:
            active_artists = [(1, 'default')]

        # Use first active artist's Spotify credentials (Spotify API is per-account)
        saas_artist_id = active_artists[0][0]
        creds = load_platform_credentials(saas_artist_id, 'spotify')
        client_id = creds.get('client_id') or os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = creds.get('client_secret') or os.getenv('SPOTIFY_CLIENT_SECRET')
        if creds.get('client_id'):
            logger.info(f'  Spotify credentials loaded from DB (artist_id={saas_artist_id})')

        # Initialiser collector
        collector = SpotifyCollector(
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Liste des artistes à suivre
        artist_ids = os.getenv('SPOTIFY_ARTIST_IDS', '').split(',')
        
        if not artist_ids or artist_ids == ['']:
            logger.warning('⚠️ Aucun artiste configuré dans SPOTIFY_ARTIST_IDS')
            return 0
        
        # ✅ Connexion à la base spotify_etl
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            #database='spotify_etl',  # ✅ Base correcte, mais on vient la récupérer dynamiquement via .env
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        artists_collected = 0
        
        for artist_id in artist_ids:
            artist_id = artist_id.strip()
            if not artist_id:
                continue
            
            logger.info(f'📊 Collecte artiste: {artist_id}')
            
            # Récupérer infos artiste
            artist_info = collector.get_artist_info(artist_id)
            
            if artist_info:
                # Stocker dans table artists
                db.upsert_many(
                    table='artists',
                    data=[artist_info],
                    conflict_columns=['artist_id'],
                    update_columns=['name', 'followers', 'popularity', 'collected_at']
                )
                
                # Stocker historique
                db.execute_query("""
                    INSERT INTO artist_history (artist_id, followers, popularity, collected_at)
                    VALUES (%s, %s, %s, %s)
                """, (
                    artist_info['artist_id'],
                    artist_info['followers'],
                    artist_info['popularity'],
                    artist_info['collected_at']
                ))
                
                artists_collected += 1
                logger.info(f'✅ Artiste {artist_id} collecté')
        
        db.close()
        
        logger.info(f'✅ Total: {artists_collected} artistes collectés')
        return artists_collected
        
    except Exception as e:
        logger.error(f'❌ Erreur collecte artistes: {e}')
        import traceback
        traceback.print_exc()
        raise


def collect_spotify_top_tracks(**context):
    """Collecte les top tracks des artistes et stocke l'historique de popularité."""
    try:
        from src.collectors.spotify_api import SpotifyCollector
        from src.database.postgres_handler import PostgresHandler
        
        logger.info('🎵 Collecte Spotify - Top Tracks...')
        
        collector = SpotifyCollector(
            client_id=os.getenv('SPOTIFY_CLIENT_ID'),
            client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
        )
        
        # ✅ Connexion à la base spotify_etl
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database='spotify_etl',  # ✅ Base correcte
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        # Récupérer les artistes depuis la DB
        artists = db.fetch_query("SELECT artist_id FROM artists")
        
        if not artists:
            logger.warning('⚠️ Aucun artiste trouvé en base. Lancez d\'abord collect_artists.')
            db.close()
            return 0
        
        total_tracks = 0
        popularity_records = []
        
        # ✅ CORRECTION : Utiliser date() depuis datetime
        current_datetime = datetime.now()
        current_date = date.today()  # ✅ Changement ici
        
        for (artist_id,) in artists:
            logger.info(f'🎵 Top tracks pour artiste: {artist_id}')
            
            # Récupérer top tracks
            tracks = collector.get_artist_top_tracks(artist_id)
            
            if tracks:
                # Stocker dans DB
                count = db.upsert_many(
                    table='tracks',
                    data=tracks,
                    conflict_columns=['track_id'],
                    update_columns=[
                        'track_name', 'popularity', 'duration_ms',
                        'album_name', 'release_date', 'collected_at'
                    ]
                )
                
                total_tracks += count
                logger.info(f'✅ {count} tracks collectées')
                
                # Préparer l'historique de popularité
                for track in tracks:
                    popularity_records.append({
                        'track_id': track['track_id'],
                        'track_name': track['track_name'],
                        'popularity': track['popularity'],
                        'collected_at': current_datetime,
                        'date': current_date
                    })
        
        # Stocker l'historique de popularité
        if popularity_records:
            logger.info(f'📊 Stockage historique popularité: {len(popularity_records)} enregistrements...')
            
            try:
                pop_count = db.upsert_many(
                    table='track_popularity_history',
                    data=popularity_records,
                    conflict_columns=['artist_id', 'track_id', 'date'],
                    update_columns=['track_name', 'popularity', 'collected_at']
                )
                
                logger.info(f'✅ {pop_count} enregistrements d\'historique stockés')
                logger.info(f'📅 Date enregistrée: {current_date}')
                
            except Exception as e:
                logger.error(f'❌ Erreur stockage historique popularité: {e}')
                import traceback
                logger.error(traceback.format_exc())
                raise
        else:
            logger.warning('⚠️ Aucun enregistrement de popularité à stocker')
        
        db.close()
        
        logger.info(f'✅ Total: {total_tracks} tracks collectées')
        logger.info(f'✅ Total: {len(popularity_records)} enregistrements de popularité créés')
        return total_tracks
        
    except Exception as e:
        logger.error(f'❌ Erreur collecte tracks: {e}')
        import traceback
        traceback.print_exc()
        raise


with DAG(
    'spotify_api_daily',
    default_args=default_args,
    description='Collecte quotidienne Spotify API (artistes + tracks + historique popularité)',
    schedule_interval=None,  
    start_date=datetime(2025, 1, 20),
    catchup=False,
    tags=['spotify', 'api', 'production'],
) as dag:
    
    # Tâche 1: Collecter les artistes
    collect_artists_task = PythonOperator(
        task_id='collect_artists',
        python_callable=collect_spotify_artists,
        provide_context=True,
    )
    
    # Tâche 2: Collecter les top tracks + historique popularité
    collect_tracks_task = PythonOperator(
        task_id='collect_top_tracks',
        python_callable=collect_spotify_top_tracks,
        provide_context=True,
    )
    
    # Définir l'ordre d'exécution
    collect_artists_task >> collect_tracks_task