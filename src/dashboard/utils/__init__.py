import os
import streamlit as st
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

# Ajout du path pour trouver les modules src
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database.postgres_handler import PostgresHandler
from src.utils.config_loader import config_loader


def get_db_connection() -> Optional[PostgresHandler]:
    """
    Create a PostgreSQL connection.

    Priority:
    1. DATABASE_URL env var (Railway / production deployment).
    2. config/config.yaml database section (local Docker dev).
    """
    try:
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            return PostgresHandler.from_url(database_url)

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


@contextmanager
def project_db() -> Iterator[PostgresHandler]:
    """Open a Postgres connection scoped to a `with` block; guarantees close.

    On connection failure, displays a Streamlit error and halts the page
    via st.stop() — no need for the caller to check for None.

    Usage:
        with project_db() as db:
            df = db.fetch_df("SELECT ...", params)
            # render
    """
    db = get_db_connection()
    if db is None:
        st.error("❌ Database unreachable. Make sure Docker is running: `docker-compose up -d`")
        st.stop()
    try:
        yield db
    finally:
        db.close()