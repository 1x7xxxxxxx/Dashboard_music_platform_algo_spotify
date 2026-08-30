"""Rule #9, asked of the render instead of of the source text.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres
Depends on: src/dashboard/views/*.py, src/database/postgres_handler.py
Persists in: nothing

Why this exists next to `test_view_connection_budget.py`
--------------------------------------------------------
That file answers rule #9 with a regex:

    len(re.findall(r"get_db_connection\\(\\)", path.read_text()))

which counts how many times a FILE types a string. Three things it cannot see:

  * `project_db()` and `view_session()` — both open a connection, neither matches;
  * a connection opened by a **callee** (a helper, a shared widget, kpi_helpers);
  * its own comments, which is how four guards written on 2026-08-22 passed on
    their own explanatory text.

Its header states "every view now opens exactly one connection per render".
Measured at runtime on 2026-08-30 by patching `PostgresHandler._connect` and
rendering each of the 42 views: **41 open one, `hypeddit` opens two.** The second
comes from a helper, which a per-file count can never attribute.

The older test keeps its ratchet and its REX — it stops the *textual* count from
growing, which is still useful. This one asks the question rule #9 actually poses:
how many connections does rendering this page open?
"""
from __future__ import annotations

import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433

# Runtime ceiling per view. A view absent from this map must open at most one.
# Lower a number when a view is fixed; never raise one.
_KNOWN_MULTI: dict[str, int] = {}
# Emptied 2026-08-30. `hypeddit` was the last at 2, and the second connection was not
# a second `get_db_connection()` — it was `_render_history()` calling `db.close()` on
# the connection `show()` owns, after which `_render_entry_form()` kept querying and
# `PostgresHandler._ensure_connection()` silently reconnected. The page worked; only
# a count taken AT THE RENDER could see it.


def _db_ready() -> bool:
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return False
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        if db is None:
            return False
        try:
            db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
            return True
        finally:
            db.close()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} — "
           "counting connections needs the real render path",
)

VIEWS = [
    "admin", "account", "airflow_kpi", "alerts", "apple_music", "billing",
    "credentials", "data_wrapped", "db_health", "etl_logs", "export_csv",
    "export_pdf", "home", "hypeddit", "imusician", "instagram", "meta_ads_overview",
    "meta_breakdowns", "meta_cpr_optimizer", "meta_creatives", "meta_mapping",
    "meta_x_spotify", "ml_performance", "perf_monitor", "process_guide",
    "promo_admin", "referral", "referral_admin", "revenue_forecast", "sacem",
    "saisie_s4a", "soundcloud", "spotify_s4a_combined", "trigger_algo", "upgrade",
    "upload_csv", "usage_analytics", "useful_links", "youtube", "onboarding",
    "onboarding_health", "register",
]

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


def connections_opened_by(view: str) -> int:
    """Render `view` and count real `PostgresHandler._connect` calls."""
    from streamlit.testing.v1 import AppTest

    from src.database.postgres_handler import PostgresHandler

    count = {"n": 0}
    original = PostgresHandler._connect

    def counting(self, *args, **kwargs):
        count["n"] += 1
        return original(self, *args, **kwargs)

    PostgresHandler._connect = counting
    try:
        at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), view=view))
        at.run(timeout=180)
    finally:
        PostgresHandler._connect = original
    return count["n"]


@pytest.mark.parametrize("view", VIEWS)
def test_rendering_a_view_opens_at_most_its_ceiling(view):
    allowed = _KNOWN_MULTI.get(view, 1)
    opened = connections_opened_by(view)
    assert opened <= allowed, (
        f"{view}.show() opened {opened} connections (ceiling {allowed}). Rule #9: a "
        "view opens exactly one and never a second as a fallback. Note the count is "
        "of the RENDER, so a connection opened by a helper counts here even though "
        "the view's own source never spells `get_db_connection()`."
    )


def test_the_ceiling_map_has_not_gone_stale():
    """A ceiling above the real count hides a fix and invites a regression back to it."""
    stale = []
    for view, allowed in _KNOWN_MULTI.items():
        opened = connections_opened_by(view)
        if opened < allowed:
            stale.append(f"{view}: now opens {opened}, ceiling still says {allowed}")
    assert not stale, (
        "lower these ceilings — a stale one lets the count climb back for free:\n  "
        + "\n  ".join(stale)
    )


def test_the_counter_actually_counts():
    """Mutation: the instrument must move when a connection is opened.

    A counter wired to nothing reports 0 for every view and the whole file passes
    while measuring nothing — the failure mode this repo has hit four times.
    """
    from src.dashboard.utils import get_db_connection
    from src.database.postgres_handler import PostgresHandler

    count = {"n": 0}
    original = PostgresHandler._connect

    def counting(self, *args, **kwargs):
        count["n"] += 1
        return original(self, *args, **kwargs)

    PostgresHandler._connect = counting
    try:
        db = get_db_connection()
        if db is not None:
            db.close()
    finally:
        PostgresHandler._connect = original
    assert count["n"] == 1, (
        f"the patch counted {count['n']} connections for exactly one open — the "
        "instrument is not attached to the code path it claims to measure."
    )
