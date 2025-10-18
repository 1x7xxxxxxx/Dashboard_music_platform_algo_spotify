"""Gestionnaire de connexion et opérations PostgreSQL."""
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from typing import Dict, List, Any, Optional
import logging
from contextlib import contextmanager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostgreSQLHandler:
    """Gère les connexions et opérations avec PostgreSQL."""
    
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        """
        Initialise le gestionnaire PostgreSQL.
        
        Args:
            host: Hôte de la base de données
            port: Port de connexion
            database: Nom de la base de données
            user: Nom d'utilisateur
            password: Mot de passe
        """
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        self._test_connection()
    
    def _test_connection(self) -> None:
        """Test la connexion à la base de données."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT version();')
                    version = cur.fetchone()[0]
                    logger.info(f"✅ Connexion PostgreSQL réussie: {version}")
        except Exception as e:
            logger.error(f"❌ Erreur de connexion PostgreSQL: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Context manager pour gérer les connexions.
        
        Yields:
            Connection PostgreSQL
        """
        conn = psycopg2.connect(**self.connection_params)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Erreur transaction: {e}")
            raise
        finally:
            conn.close()
    
    def create_tables(self) -> None:
        """Crée les tables nécessaires si elles n'existent pas."""
        
        tables = {
            'artists': """
                CREATE TABLE IF NOT EXISTS artists (
                    artist_id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    followers INTEGER,
                    popularity INTEGER,
                    genres TEXT[],
                    collected_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """,
            'tracks': """
                CREATE TABLE IF NOT EXISTS tracks (
                    track_id VARCHAR(50) PRIMARY KEY,
                    track_name VARCHAR(255) NOT NULL,
                    artist_id VARCHAR(50) REFERENCES artists(artist_id),
                    popularity INTEGER,
                    duration_ms INTEGER,
                    explicit BOOLEAN,
                    album_name VARCHAR(255),
                    release_date DATE,
                    collected_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """,
            'audio_features': """
                CREATE TABLE IF NOT EXISTS audio_features (
                    id SERIAL PRIMARY KEY,
                    track_id VARCHAR(50) REFERENCES tracks(track_id),
                    danceability FLOAT,
                    energy FLOAT,
                    key INTEGER,
                    loudness FLOAT,
                    mode INTEGER,
                    speechiness FLOAT,
                    acousticness FLOAT,
                    instrumentalness FLOAT,
                    liveness FLOAT,
                    valence FLOAT,
                    tempo FLOAT,
                    collected_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(track_id, collected_at)
                );
            """,
            'artist_history': """
                CREATE TABLE IF NOT EXISTS artist_history (
                    id SERIAL PRIMARY KEY,
                    artist_id VARCHAR(50) REFERENCES artists(artist_id),
                    followers INTEGER,
                    popularity INTEGER,
                    collected_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_artist_history_date 
                ON artist_history(artist_id, collected_at DESC);
            """
        }
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    for table_name, create_sql in tables.items():
                        cur.execute(create_sql)
                        logger.info(f"✅ Table '{table_name}' créée/vérifiée")
            
            logger.info("✅ Toutes les tables sont prêtes")
            
        except Exception as e:
            logger.error(f"❌ Erreur création des tables: {e}")
            raise
    
    def insert_artist(self, artist_data: Dict[str, Any]) -> None:
        """
        Insert ou met à jour un artiste.
        
        Args:
            artist_data: Données de l'artiste
        """
        sql = """
            INSERT INTO artists (artist_id, name, followers, popularity, genres, collected_at)
            VALUES (%(artist_id)s, %(name)s, %(followers)s, %(popularity)s, %(genres)s, %(collected_at)s)
            ON CONFLICT (artist_id) 
            DO UPDATE SET
                name = EXCLUDED.name,
                followers = EXCLUDED.followers,
                popularity = EXCLUDED.popularity,
                genres = EXCLUDED.genres,
                collected_at = EXCLUDED.collected_at,
                updated_at = CURRENT_TIMESTAMP;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, artist_data)
            logger.info(f"✅ Artiste '{artist_data['name']}' inséré/mis à jour")
        except Exception as e:
            logger.error(f"❌ Erreur insertion artiste: {e}")
            raise
    
    def insert_artist_history(self, artist_data: Dict[str, Any]) -> None:
        """
        Insert l'historique d'un artiste.
        
        Args:
            artist_data: Données de l'artiste
        """
        sql = """
            INSERT INTO artist_history (artist_id, followers, popularity, collected_at)
            VALUES (%(artist_id)s, %(followers)s, %(popularity)s, %(collected_at)s);
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, artist_data)
            logger.info(f"✅ Historique artiste '{artist_data['artist_id']}' ajouté")
        except Exception as e:
            logger.error(f"❌ Erreur insertion historique: {e}")
            raise
    
    def insert_tracks(self, tracks_data: List[Dict[str, Any]]) -> None:
        """
        Insert ou met à jour plusieurs tracks.
        
        Args:
            tracks_data: Liste des données de tracks
        """
        if not tracks_data:
            return
        
        sql = """
            INSERT INTO tracks (track_id, track_name, artist_id, popularity, 
                              duration_ms, explicit, album_name, release_date, collected_at)
            VALUES %s
            ON CONFLICT (track_id) 
            DO UPDATE SET
                track_name = EXCLUDED.track_name,
                popularity = EXCLUDED.popularity,
                collected_at = EXCLUDED.collected_at,
                updated_at = CURRENT_TIMESTAMP;
        """
        
        try:
            values = [
                (
                    track['track_id'],
                    track['track_name'],
                    track['artist_id'],
                    track['popularity'],
                    track['duration_ms'],
                    track['explicit'],
                    track['album_name'],
                    track['release_date'],
                    track['collected_at']
                )
                for track in tracks_data
            ]
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    execute_values(cur, sql, values)
            
            logger.info(f"✅ {len(tracks_data)} tracks insérés/mis à jour")
        except Exception as e:
            logger.error(f"❌ Erreur insertion tracks: {e}")
            raise
    
    def get_artist_stats(self, artist_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        Récupère les statistiques historiques d'un artiste.
        
        Args:
            artist_id: ID de l'artiste
            days: Nombre de jours d'historique
            
        Returns:
            Liste des statistiques
        """
        sql = """
            SELECT artist_id, followers, popularity, collected_at
            FROM artist_history
            WHERE artist_id = %s 
            AND collected_at >= NOW() - INTERVAL '%s days'
            ORDER BY collected_at DESC;
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, (artist_id, days))
                    results = cur.fetchall()
            
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"❌ Erreur récupération stats: {e}")
            return []


# Test du module
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.utils.config_loader import config_loader
    
    # Charger la config
    config = config_loader.load()
    db_config = config['database']
    
    # Créer le handler
    db = PostgreSQLHandler(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )
    
    # Créer les tables
    db.create_tables()
    
    print("\n✅ Base de données prête !")