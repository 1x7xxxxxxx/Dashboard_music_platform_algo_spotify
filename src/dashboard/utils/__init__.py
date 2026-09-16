import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

# Ajout du path pour trouver les modules src
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database.postgres_handler import PostgresHandler
# `config_loader` is no longer imported here: the config.yaml fallback moved
# into `PostgresHandler.from_env_or_config()`, which is the single place that
# knows the DATABASE_URL → DATABASE_* → config.yaml precedence.

# ── `logo_html` a DÉMÉNAGÉ dans `branding.py` (2026-09-16) ────────────────────
# Elle portait un `@st.cache_data`, et un décorateur s'évalue À L'IMPORT : cette
# seule ligne imposait `import streamlit` en tête de ce module, donc **5,30 s** à
# quiconque ne voulait qu'une connexion Postgres — 50 fichiers de tests, l'API, tout
# script de base. Rien d'autre ici n'a besoin de Streamlit AVANT d'être appelé.
#
# `from src.dashboard.utils import logo_html` continue de fonctionner : le nom est
# réexporté ci-dessous, en import PARESSEUX, pour ne pas ramener ce qu'on vient de
# sortir. Les deux appelants (`app.py`, `auth.py`) l'importent déjà dans une fonction.
# Garde : tests/test_the_db_door_does_not_pull_a_framework.py


def logo_html(variant: str = "dark", max_width: int = 220, center: bool = False) -> str:
    """Réexport paresseux de `branding.logo_html` — voir le commentaire ci-dessus."""
    from src.dashboard.utils.branding import logo_html as _impl
    return _impl(variant=variant, max_width=max_width, center=center)


def get_db_connection() -> Optional[PostgresHandler]:
    """Create a PostgreSQL connection for a dashboard page. None on failure.

    Delegates to `PostgresHandler.from_env_or_config()` — the one place that knows
    the precedence `DATABASE_URL` → the `DATABASE_*` variables → `config.yaml`.

    This function used to restate that precedence and skip the middle step, and the
    omission was not theoretical. Measured in production on 2026-08-22:

        streamlytics_dashboard / streamlytics_api : DATABASE_URL only
        airflow_scheduler                          : DATABASE_HOST/NAME/USER only
        every container                            : no config.yaml at all

    So the two halves of the product reached one database through two mechanisms,
    neither of which worked in the other's place. Setting `DATABASE_HOST` on the
    dashboard, or `DATABASE_URL` on the scheduler, silently broke that half — the
    dashboard falling through to a `config.yaml` that does not exist.

    The Streamlit-specific part stays here, and only that: turning a failure into a
    red banner and a None, because a view must degrade rather than crash.
    """
    # Le pool et le cache s'arment au PREMIER besoin de connexion du processus, une
    # seule fois chacun. Ici plutôt qu'à l'import : un import ne doit pas ouvrir de
    # socket, et les tests importent ce module sans base.
    #
    # ILS ONT ÉTÉ DÉBRANCHÉS DEUX FOIS SUR UN FAUX DIAGNOSTIC, le 2026-09-11, et
    # c'est la partie à retenir. La CI comptait 21 puis 23 requêtes sur l'accueil au
    # lieu de 13 ; j'ai accusé le pool, puis le cache, et débranché les deux. Aucun
    # des deux n'y était pour rien : la page coûte simplement DEUX PRIX selon que la
    # mise en route du locataire est finie ou non — terminée elle lit ses sections de
    # données, inachevée elle rend EN PLUS la matrice de mise en route, soit dix
    # requêtes. La base locale avait un artiste configuré, celle de la CI est neuve.
    # Le test comparait donc deux ÉTATS, pas deux versions du code.
    #
    # Une fois l'état du locataire épinglé dans la mesure
    # (`tests/test_a_page_asks_the_same_question_once.py`), les deux rebranchés
    # passent à 13 sur une base neuve. Gains mesurés en production : ~40 ms de
    # poignées de main évitées par le pool, et l'accueil artiste de 13 à 11 requêtes
    # par le cache.
    from src.database.postgres_handler import enable_pool
    enable_pool(minconn=1, maxconn=8)
    from src.dashboard.utils.series_cache import install as _install_series_cache
    _install_series_cache()

    try:
        return PostgresHandler.from_env_or_config()
    except Exception as e:
        # Import LOCAL : ce module est la porte de la base, pas une surface d'UI.
        # Le chemin d'échec est le seul qui parle à un humain, et il n'est pris que
        # dans un processus Streamlit, où le module est déjà chargé.
        import streamlit as st
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
    import streamlit as st

    from src.dashboard.utils.i18n import t
    db = get_db_connection()
    if db is None:
        st.error(t("ui.db_unreachable",
                   "❌ Database unreachable. Make sure Docker is running: `docker-compose up -d`"))
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
    import streamlit as st

    from src.dashboard.auth import get_artist_id, is_admin
    from src.dashboard.utils.i18n import t
    # The tenant is resolved BEFORE the connection is opened, and the order is
    # the fix, not a style choice. `st.stop()` raises `StopException`; it used to
    # be raised between the open and the `try`, so the `finally` never ran and
    # the connection leaked. Invisible with one user — under concurrency those
    # sockets accumulate against `max_connections` (100, default, shared with
    # Airflow and the API), and the symptom is not slowness but a refused
    # connection. Resolving first means there is nothing open to leak.
    artist_id = get_artist_id()
    if artist_id is None:
        if not is_admin():
            st.error(t("ui.invalid_session", "Session invalide."))
            st.stop()
        artist_id = 1  # admin fallback — full cross-tenant view (Admin panel)
    db = get_db_connection()
    # Une écriture faite par une AUTRE instance rend nos compteurs faux sans que rien
    # ici ne le sache : `clear_kpi_caches()` ne purge que son propre processus. Cette
    # ligne est l'unique endroit où ce dépôt le découvre — au seuil du rendu, avant que
    # la vue ne lise quoi que ce soit de caché. Coût : une requête par processus toutes
    # les 30 s, pas une par rendu. Détail et compromis dans `cache_epoch.py`.
    try:
        from src.dashboard.utils.cache_epoch import honour_remote_invalidation
        honour_remote_invalidation(artist_id, db)
    except Exception:  # noqa: BLE001 — jamais au prix du rendu
        pass
    try:
        yield db, artist_id
    finally:
        if db is not None:
            db.close()
