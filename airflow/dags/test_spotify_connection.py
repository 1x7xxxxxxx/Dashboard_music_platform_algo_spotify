"""DAG de test pour vérifier la connexion Spotify."""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
import logging

sys.path.insert(0, '/opt/airflow')

from dotenv import load_dotenv
load_dotenv('/opt/airflow/.env')

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'retries': 0,
}


def test_spotify_connection(**context):
    """Test de connexion Spotify."""
    try:
        logger.info("="*70)
        logger.info("🧪 TEST CONNEXION SPOTIFY")
        logger.info("="*70)
        
        # Vérifier les variables d'environnement
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        artist_ids = os.getenv('SPOTIFY_ARTIST_IDS')
        
        logger.info(f"CLIENT_ID présent: {'✅ OUI' if client_id else '❌ NON'}")
        logger.info(f"CLIENT_SECRET présent: {'✅ OUI' if client_secret else '❌ NON'}")
        logger.info(f"ARTIST_IDS: {artist_ids}")
        
        if not client_id or not client_secret:
            raise ValueError("❌ Credentials Spotify manquants dans l'environnement Docker")
        
        # Test de connexion
        from src.collectors.spotify_api import SpotifyCollector
        
        collector = SpotifyCollector(
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Test avec Daft Punk
        test_artist = collector.get_artist_info('4tZwfgrHOc3mvqYlEYSvVi')
        
        if test_artist:
            logger.info(f"✅ Connexion réussie !")
            logger.info(f"✅ Test artiste: {test_artist['name']}")
            logger.info(f"✅ Followers: {test_artist['followers']:,}")
            logger.info(f"✅ Type collected_at: {type(test_artist['collected_at'])}")
        else:
            raise ValueError("❌ Échec récupération artiste de test")
        
        # Vérifier la DB
        from src.database.postgres_handler import PostgresHandler
        
        db = PostgresHandler(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            database=os.getenv('DATABASE_NAME', 'spotify_etl'),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD')
        )
        
        # Test d'insertion
        logger.info("📊 Test insertion en base...")
        
        db.upsert_many(
            table='artists',
            data=[test_artist],
            conflict_columns=['artist_id'],
            update_columns=['name', 'followers', 'popularity', 'collected_at']
        )
        
        logger.info("✅ Insertion réussie !")
        
        db.close()
        
        logger.info("="*70)
        logger.info("🎉 TOUS LES TESTS PASSÉS")
        logger.info("="*70)
        
        return "success"
        
    except Exception as e:
        logger.error(f"❌ ERREUR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


with DAG(
    'test_spotify_connection',
    default_args=default_args,
    description='Test connexion Spotify et DB',
    schedule_interval=None,
    start_date=datetime(2025, 1, 20),
    catchup=False,
    tags=['test', 'spotify'],
) as dag:
    
    test_task = PythonOperator(
        task_id='test_connection',
        python_callable=test_spotify_connection,
        provide_context=True,
    )