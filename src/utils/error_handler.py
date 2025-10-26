# Créer src/utils/error_handler.py

import logging
from functools import wraps
from datetime import datetime

def log_errors(func):
    """Décorateur pour logger les erreurs."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Erreur dans {func.__name__}: {e}")
            logger.error(f"   Args: {args}")
            logger.error(f"   Kwargs: {kwargs}")
            
            # Enregistrer en DB pour historique
            from src.database.postgres_handler import PostgresHandler
            db = PostgresHandler(...)
            db.execute_query("""
                INSERT INTO error_logs (function_name, error_message, timestamp)
                VALUES (%s, %s, %s)
            """, (func.__name__, str(e), datetime.now()))
            
            raise
    return wrapper