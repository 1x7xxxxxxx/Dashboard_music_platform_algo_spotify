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

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


@st.cache_data
def logo_html(variant: str = "dark", max_width: int = 220, center: bool = False) -> str:
    """streaMLytics wordmark as a base64 data-URI <img> (SVG renders reliably).

    variant: 'dark' (dark text, light bg) | 'light' (white text, dark bg).
    """
    import base64
    name = {
        "light": "logo_horizontal_light.svg",
        "dark": "logo_horizontal_dark.svg",
        "adaptive": "logo_horizontal_adaptive.svg",
    }.get(variant, "logo_horizontal_adaptive.svg")
    try:
        b64 = base64.b64encode((_ASSETS_DIR / name).read_bytes()).decode("ascii")
    except Exception:
        return ""
    img = (f'<img src="data:image/svg+xml;base64,{b64}" '
           f'style="width:100%;max-width:{max_width}px;" alt="streaMLytics"/>')
    if center:
        return f'<div style="text-align:center;margin:8px 0 18px 0;">{img}</div>'
    return img


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


@contextmanager
def view_session() -> Iterator[tuple[PostgresHandler, int]]:
    """DB connection + resolved tenant artist_id for a view's show().

    Factors the boilerplate repeated verbatim across ~30 views and enforces
    CLAUDE.md rule #7 (never `get_artist_id() or 1`) and rule #9 (one
    connection per show()) structurally. Behaviour-identical to the inline
    block, including the non-admin `st.stop()` BEFORE the try (so an invalid
    session never reaches the body), and admin → artist_id = 1.

    Usage:
        def show():
            with view_session() as (db, artist_id):
                ...  # body; connection closed automatically
    """
    from src.dashboard.auth import get_artist_id, is_admin
    db = get_db_connection()
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error("Session invalide.")
            st.stop()
        artist_id = 1  # admin fallback — full cross-tenant view (Admin panel)
    try:
        yield db, artist_id
    finally:
        if db is not None:
            db.close()
