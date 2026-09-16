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


def track_page_view(page: str) -> None:
    """page_view deduped per session — Streamlit reruns on every widget interaction,
    so only the first render of each distinct page is logged."""
    if not page:
        return
    if st.session_state.get("_last_tracked_page") == page:
        return
    st.session_state["_last_tracked_page"] = page
    track("page_view", page=page)
