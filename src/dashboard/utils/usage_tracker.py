"""First-party product-usage tracking — fail-silent server-side event log.

Type: Utility
Persists in: usage_events
Uses: PostgresHandler, st.session_state

Telemetry MUST NEVER raise or slow a page → every path is wrapped and swallowed
(the deliberate inverse of the collector "must raise" rule). A failed track is a
lost event, never a broken page.
"""
import json
import os
import uuid

import streamlit as st


def _session_id() -> str:
    sid = st.session_state.get("_session_id")
    if not sid:
        sid = uuid.uuid4().hex
        st.session_state["_session_id"] = sid
    return sid


def _connect():
    """Short-lived connection WITHOUT the st.error side effect of get_db_connection."""
    from src.database.postgres_handler import PostgresHandler
    from src.utils.config_loader import config_loader

    url = os.environ.get("DATABASE_URL")
    if url:
        return PostgresHandler.from_url(url)
    cfg = config_loader.load()["database"]
    return PostgresHandler(
        host=cfg["host"], port=cfg["port"], database=cfg["database"],
        user=cfg["user"], password=cfg["password"],
    )


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
