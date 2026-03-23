"""Handler pour les interactions avec PostgreSQL - VERSION OPTIMISÉE."""
import psycopg2
from psycopg2.extras import execute_values
from typing import List, Dict, Any, Optional, Tuple
import logging

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

            # ✅ AUTOCOMMIT : Chaque requête est committée immédiatement
            self.conn.autocommit = True

            self.cursor = self.conn.cursor()
            logger.info(f"✅ Connecté à PostgreSQL: {self.database}")
        except Exception as e:
            logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
            raise

    def _ensure_connection(self) -> None:
        """Reconnecte automatiquement si la connexion est perdue."""
        try:
            if self.conn is None or self.conn.closed:
                logger.warning("⚠️ Connexion PostgreSQL perdue — reconnexion automatique...")
                self._connect()
                return
            # Test léger de connexion via poll()
            self.conn.poll()
        except psycopg2.OperationalError:
            logger.warning("⚠️ Connexion PostgreSQL interrompue — reconnexion automatique...")
            self._connect()
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> None:
        """
        Exécute une requête SQL (INSERT, UPDATE, DELETE, CREATE).
        
        Args:
            query: Requête SQL
            params: Paramètres de la requête
        """
        self._ensure_connection()
        try:
            self.cursor.execute(query, params)
            # ✅ Pas de commit nécessaire avec autocommit = True
            logger.debug(f"✅ Requête exécutée")
        except Exception as e:
            logger.error(f"❌ Erreur exécution requête: {e}")
            logger.error(f"   Query: {query[:200]}...")
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
        self._ensure_connection()
        try:
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            logger.debug(f"✅ Fetch query retourné {len(results)} lignes")
            return results
        except Exception as e:
            logger.error(f"❌ Erreur fetch requête: {e}")
            logger.error(f"   Query: {query[:200]}...")
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
        self._ensure_connection()
        try:
            import pandas as pd
            self.cursor.execute(query, params)
            columns = [desc[0] for desc in self.cursor.description]
            data = self.cursor.fetchall()
            df = pd.DataFrame(data, columns=columns)
            logger.debug(f"✅ Fetch DataFrame retourné {len(df)} lignes")
            return df
        except Exception as e:
            logger.error(f"❌ Erreur fetch DataFrame: {e}")
            logger.error(f"   Query: {query[:200]}...")
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
            logger.warning(f"⚠️ insert_many appelé avec data vide pour {table}")
            return 0
        
        try:
            columns = list(data[0].keys())
            values = [[row.get(col) for col in columns] for row in data]
            
            columns_str = ', '.join(columns)
            placeholders = ', '.join(['%s'] * len(columns))
            
            query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
            
            self.cursor.executemany(query, values)
            # ✅ Pas de commit nécessaire avec autocommit = True
            
            logger.info(f"✅ {len(data)} ligne(s) insérée(s) dans {table}")
            return len(data)
        except Exception as e:
            logger.error(f"❌ Erreur insert_many sur {table}: {e}")
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
            logger.warning(f"⚠️ upsert_many appelé avec data vide pour {table}")
            return 0

        self._ensure_connection()
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
            rows_affected = self.cursor.rowcount
            # ✅ Pas de commit nécessaire avec autocommit = True
            
            logger.info(f"✅ {rows_affected} ligne(s) affectée(s) dans {table}")
            
            return rows_affected
        except Exception as e:
            logger.error(f"❌ Erreur upsert_many sur {table}: {e}")
            logger.error(f"   Data sample: {data[0] if data else 'empty'}")
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
        try:
            query = f"SELECT COUNT(*) FROM {table_name}"
            result = self.fetch_query(query)
            count = result[0][0] if result else 0
            logger.debug(f"📊 Table {table_name}: {count} lignes")
            return count
        except Exception as e:
            logger.error(f"❌ Erreur get_table_count pour {table_name}: {e}")
            return 0
    
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