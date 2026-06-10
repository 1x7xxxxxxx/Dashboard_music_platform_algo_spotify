"""Render-smoke tests for every dashboard view.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres (spotify_etl)
Depends on: src/dashboard/views/*.show(), a reachable DB on localhost:5433
Persists in: —

Each view's `show()` is executed inside a Streamlit `AppTest` script context with a
minimal admin session. The single assertion is "no uncaught exception" — this catches
import-scope regressions (e.g. a `NameError` from a mis-scoped lazy `import plotly`),
broken `@st.fragment` refactors, and SQL/identifier typos that only fire at render time.
The committed suite previously had ZERO view-render coverage, so any such regression
shipped silently (see DEVLOG WAVE 3 "failed-Edit dead code passed tests+ruff").

The whole module is SKIPPED when Postgres is unreachable (CI has no live DB on 5433),
so it adds value locally without breaking CI. Views render against real data as admin
(role='admin' → premium plan, no tenant filter), exercising the real query paths.
"""
import socket

import pytest

# ── DB readiness gate ────────────────────────────────────────────────────────
# Views open a real connection via get_db_connection() and query real tables, so
# skip the whole module unless a *provisioned* Postgres is up. A TCP check alone is
# insufficient: CI starts an EMPTY `postgres:17` service on 5433 (schema never
# migrated), so the socket connects but every view fails with 'relation … does not
# exist'. Gate on a core table's presence so the suite runs locally (real populated
# DB) and skips cleanly against an unprovisioned CI DB.
_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db_ready() -> bool:
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            pass
    except OSError:
        return False
    # Socket is up — confirm the app schema is actually loaded (a core table exists).
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        try:
            db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} "
           "(socket down or schema not migrated) — render-smoke needs the live DB",
)

# Every view wired into app.py's dispatch (src/dashboard/app.py). Keep in sync when
# adding a view (the same step that adds it to _NAV_SECTIONS).
VIEWS = [
    "admin", "account", "airflow_kpi", "alerts", "apple_music", "billing",
    "credentials", "data_wrapped", "db_health", "etl_logs", "export_csv",
    "export_pdf", "home", "hypeddit", "imusician", "instagram", "meta_ads_overview",
    "meta_breakdowns", "meta_cpr_optimizer", "meta_creatives", "meta_mapping",
    "meta_x_spotify", "ml_performance", "perf_monitor", "process_guide",
    "promo_admin", "referral", "referral_admin",
    "revenue_forecast", "saisie_s4a", "soundcloud",
    "spotify_s4a_combined", "trigger_algo", "upgrade", "upload_csv", "useful_links",
    "youtube",
]

# AppTest re-execs a script string in a fresh interpreter path, so the script must
# re-inject the repo root and seed an admin session before importing the view.
_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"
st.session_state["artist_id"] = 1
st.session_state["email"] = "admin@test"
st.session_state["authenticated"] = True
from src.dashboard.views.{view} import show
show()
"""


@pytest.mark.parametrize("view", VIEWS)
def test_view_renders_without_exception(view):
    import os

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), view=view))
    at.run(timeout=90)

    if at.exception:
        ex = at.exception[0]
        detail = getattr(ex, "value", ex)
        pytest.fail(f"{view}.show() raised {type(detail).__name__}: {detail}")
