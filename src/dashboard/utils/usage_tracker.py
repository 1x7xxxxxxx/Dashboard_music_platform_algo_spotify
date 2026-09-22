"""First-party product-usage tracking — fail-silent server-side event log.

Type: Utility
Persists in: usage_events
Uses: PostgresHandler, st.session_state

Telemetry MUST NEVER raise or slow a page → every path is wrapped and swallowed
(the deliberate inverse of the collector "must raise" rule). A failed track is a
lost event, never a broken page.
"""
import json
import uuid

import streamlit as st


def _session_id() -> str:
    sid = st.session_state.get("_session_id")
    if not sid:
        sid = uuid.uuid4().hex
        st.session_state["_session_id"] = sid
    return sid


def session_id_courant() -> str:
    """L'identifiant de la session EN COURS, pour qui a besoin de le reporter.

    Exposé le 2026-09-22 pour l'entonnoir d'inscription. `auth.py` efface tout le
    `session_state` à la connexion (défense contre la fixation de session,
    MEDIUM-01), donc la session anonyme qui a vu l'écran de connexion et la session
    authentifiée qui en sort portent deux identifiants différents. Sans un report
    explicite, les deux moitiés de l'entonnoir ne se recousent pas.

    Ce n'est pas un jeton : il ne donne accès à rien et ne sert qu'à la télémétrie.
    """
    return _session_id()


def _connect():
    """Connexion courte, SANS l'effet de bord `st.error` de `get_db_connection`.

    ⚠️ Elle résolvait ses identifiants à la main jusqu'au 2026-09-17 —
    `DATABASE_URL`, sinon `config.yaml` — en sautant l'étape du milieu, les variables
    `DATABASE_*`. C'est **exactement** le défaut que la docstring de
    `from_env_or_config` raconte : *« trois collecteurs refaisaient chacun les mêmes
    cinq `os.getenv`, tous avec `localhost` par défaut, faux à l'endroit même où ils
    tournent »*. Celui-ci était le quatrième, écrit après la correction des trois.

    Ce que ça coûtait concrètement : dans un environnement qui donne `DATABASE_HOST`
    sans `DATABASE_URL` — c'est le cas d'Airflow — on retombait sur `config.yaml`, que
    les conteneurs n'embarquent pas ; `config_loader.load()["database"]` lève, le
    `except Exception: return` de `track()` avale, et **tous les évènements d'usage
    sont perdus en silence**. La télémétrie qui ne doit jamais casser la page ne doit
    pas non plus disparaître sans le dire.

    ⚠️ Et ce n'était PAS un contournement du pool, contrairement à ce que R120
    affirmait : `PostgresHandler.__init__` appelle `_connect()`, qui emprunte au pool
    quand il existe. Cette fonction y passait déjà.
    """
    from src.database.postgres_handler import PostgresHandler

    return PostgresHandler.from_env_or_config()


def track(event: str, page: str | None = None, meta: dict | None = None) -> None:
    """Log one usage event. Never raises (telemetry must not break the app)."""
    try:
        db = _connect()
    except Exception:
        return
    try:
        db.execute_query(
            "INSERT INTO usage_events (artist_id, role, session_id, event, page, meta) "
            "VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
            (
                st.session_state.get("artist_id"),
                st.session_state.get("role"),
                _session_id(),
                event,
                page,
                json.dumps(meta) if meta else None,
            ),
        )
    except Exception:
        pass
    finally:
        try:
            db.close()
        except Exception:
            pass


def track_login() -> None:
    """L'évènement de connexion, AVEC le fil vers la session anonyme d'avant.

    `meta->>'session_avant'` est ce qui rend l'entonnoir interrogeable :

        SELECT count(DISTINCT session_id) FROM usage_events WHERE page = 'login'
        -- combien ont VU l'écran
        SELECT count(*) FROM usage_events WHERE event = 'login'
        -- combien sont entrés
        -- et le fil relie les deux, malgré l'effacement de session
    """
    avant = st.session_state.pop("_session_id_avant_connexion", None)
    track("login", meta={"session_avant": avant} if avant else None)


def track_page_view(page: str) -> None:
    """page_view deduped per session — Streamlit reruns on every widget interaction,
    so only the first render of each distinct page is logged."""
    if not page:
        return
    if st.session_state.get("_last_tracked_page") == page:
        return
    st.session_state["_last_tracked_page"] = page
    track("page_view", page=page)
