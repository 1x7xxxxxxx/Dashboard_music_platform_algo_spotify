import streamlit as st
import sys
from pathlib import Path

# Ajout du path pour trouver les modules src
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader

def get_db_connection():
    """
    Crée une connexion unique à la base de données.
    Utilisée par toutes les vues.
    """
    try:
        config = config_loader.load()
        db_config = config['database']
        
        return PostgresHandler(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password']
        )
    except Exception as e:
        st.error(f"❌ Erreur de connexion BDD : {e}")
        return None