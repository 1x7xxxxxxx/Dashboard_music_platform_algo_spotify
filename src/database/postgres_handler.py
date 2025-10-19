"""Handler pour les interactions avec PostgreSQL."""
import psycopg2
from psycopg2.extras import execute_values
from typing import List, Dict, Any, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostgresHandler:
    """Gestionnaire de connexion et opérations PostgreSQL."""
    
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        """
        Initialise la connexion PostgreSQL.
        
        Args:
            host: Hôte PostgreSQL
            port: Port PostgreSQL
            database: Nom de la base de données
            user: Utilisateur
            password: Mot de passe
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.conn = None
        self.cursor = None
        
        self._connect()
    
    def _connect(self) -> None:
        """Établit la connexion à PostgreSQL."""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            self.cursor = self.conn.cursor()
            logger.info(f"✅ Connecté à PostgreSQL: {self.database}")
        except Exception as e:
            logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
            raise
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> None:
        """
        Exécute une requête SQL (INSERT, UPDATE, DELETE, CREATE).
        
        Args:
            query: Requête SQL
            params: Paramètres de la requête
        """
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Erreur exécution requête: {e}")
            raise
    
    def fetch_query(self, query: str, params: Optional[Tuple] = None) -> List[Tuple]:
        """
        Exécute une requête SELECT et retourne les résultats.
        
        Args:
            query: Requête SQL SELECT
            params: Paramètres de la requête
            
        Returns:
            Liste de tuples avec les résultats
        """
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ Erreur fetch requête: {e}")
            raise
    
    def fetch_df(self, query: str, params: Optional[Tuple] = None):
        """
        Exécute une requête SELECT et retourne un DataFrame pandas.
        
        Args:
            query: Requête SQL SELECT
            params: Paramètres de la requête
            
        Returns:
            DataFrame pandas
        """
        try:
            import pandas as pd
            self.cursor.execute(query, params)
            columns = [desc[0] for desc in self.cursor.description]
            data = self.cursor.fetchall()
            return pd.DataFrame(data, columns=columns)
        except Exception as e:
            logger.error(f"❌ Erreur fetch DataFrame: {e}")
            raise
    
    def insert_many(self, table: str, data: List[Dict[str, Any]]) -> int:
        """
        Insert multiple rows efficacement.
        
        Args:
            table: Nom de la table
            data: Liste de dictionnaires {colonne: valeur}
            
        Returns:
            Nombre de lignes insérées
        """
        if not data:
            return 0
        
        try:
            columns = list(data[0].keys())
            values = [[row.get(col) for col in columns] for row in data]
            
            columns_str = ', '.join(columns)
            placeholders = ', '.join(['%s'] * len(columns))
            
            query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
            
            self.cursor.executemany(query, values)
            self.conn.commit()
            
            return len(data)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Erreur insert_many: {e}")
            raise
    
    def upsert_many(self, table: str, data: List[Dict[str, Any]], 
                    conflict_columns: List[str], update_columns: List[str]) -> int:
        """
        Upsert (INSERT ... ON CONFLICT UPDATE) multiple rows.
        
        Args:
            table: Nom de la table
            data: Liste de dictionnaires
            conflict_columns: Colonnes pour détection conflit
            update_columns: Colonnes à mettre à jour si conflit
            
        Returns:
            Nombre de lignes affectées
        """
        if not data:
            return 0
        
        try:
            columns = list(data[0].keys())
            values = [[row.get(col) for col in columns] for row in data]
            
            columns_str = ', '.join(columns)
            conflict_str = ', '.join(conflict_columns)
            update_str = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_columns])
            
            query = f"""
                INSERT INTO {table} ({columns_str})
                VALUES %s
                ON CONFLICT ({conflict_str})
                DO UPDATE SET {update_str}
            """
            
            execute_values(self.cursor, query, values)
            self.conn.commit()
            
            return self.cursor.rowcount
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Erreur upsert_many: {e}")
            raise
    
    def table_exists(self, table_name: str) -> bool:
        """Vérifie si une table existe."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """
        result = self.fetch_query(query, (table_name,))
        return result[0][0] if result else False
    
    def get_table_count(self, table_name: str) -> int:
        """Retourne le nombre de lignes dans une table."""
        query = f"SELECT COUNT(*) FROM {table_name}"
        result = self.fetch_query(query)
        return result[0][0] if result else 0
    
    def close(self) -> None:
        """Ferme la connexion PostgreSQL."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("🔒 Connexion PostgreSQL fermée")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()