"""A session with a role but no tenant must read nothing, on every view.

Installed 2026-08-22 (R25). `get_artist_id()` returns None for two situations that
have nothing to do with each other — "this is an admin, show everything" and "this
session has no tenant" — and its own docstring has always told callers to separate
them with `is_admin()`. Five call sites did not, including `artist_id_sql_filter()`,
which is how roughly thirty views reach the database. In all five, a missing id read
as "no filter".

The state is `role='artist'` with `artist_id IS NULL`. Nothing wired produces it
today: it needs `DELETE FROM saas_artists` (`admin.py`, `ON DELETE SET NULL` in
`migrations/007:9`) and that function is dead code, the live GDPR path deleting
`saas_users` first. What is true is that the schema can hold it, an existing function
would create it, and the views had nothing against it.

Why a behavioural test rather than a grep for `get_artist_id`: the defect is not the
call, it is what the value is allowed to mean downstream. A view may call
`get_artist_id()` perfectly safely, and a view that never calls it can still leak
through a helper. So this seeds the state and looks at what comes out.
"""
import os

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

# Views that read tenant-scoped data. A view absent from this list is either
# tenant-free by nature (useful_links, process_guide, upgrade) or admin-only, where
# the role gate answers first.
TENANT_VIEWS = [
    "home", "spotify_s4a_combined", "export_pdf", "export_csv", "imusician",
    "soundcloud", "youtube", "instagram", "apple_music", "data_wrapped",
    "credentials", "account", "billing", "alerts", "onboarding",
    "onboarding_health", "saisie_s4a", "upload_csv", "meta_ads_overview",
    "meta_x_spotify", "referral", "sacem", "trigger_algo",
]

# A session that has authenticated as an artist and carries no tenant.
# The spy is installed INSIDE the script, before the view is imported, so it is in
# place for module-scope queries too.
_STRAY = """
import sys
sys.path.insert(0, {root!r})
from tests.query_spy import install
install()
import streamlit as st
st.session_state["role"] = "artist"
st.session_state["artist_id"] = None
st.session_state["user_id"] = -1
st.session_state["email"] = "stray@test"
st.session_state["authenticated"] = True
from src.dashboard.views.{view} import show
show()
"""


@pytest.mark.parametrize("view", TENANT_VIEWS)
def test_a_stray_session_reads_no_tenant_data(view):
    """The measurement is on the queries, not on the message.

    A view may refuse this session in its own words — `upload_csv` does, more
    clearly than the shared guard — and that is fine. What is not fine is reaching
    a tenant table without a tenant.
    """
    from streamlit.testing.v1 import AppTest

    from tests import query_spy

    query_spy.RECORDED.clear()
    at = AppTest.from_string(_STRAY.format(root=os.getcwd(), view=view))
    at.run(timeout=90)

    if at.exception:
        ex = at.exception[0]
        detail = getattr(ex, "value", ex)
        pytest.fail(f"{view}.show() raised {type(detail).__name__}: {detail}")

    offenders = query_spy.unscoped_tenant_reads()
    assert not offenders, (
        f"{view} read {len(offenders)} tenant table(s) for a session with "
        f"role='artist' and no tenant. First:\n{offenders[0][:400]}\n"
        "With no id to filter on, that query returns every tenant's rows."
    )

    # Non-vacuity, per view. Every view currently refuses this session before its
    # first query, so `offenders` is empty for a good reason — and would be just as
    # empty if the view had never run at all (a renamed module, a `show()` that
    # returns immediately, an AppTest that swallowed the script). The refusal has to
    # be visible, so require the view to SAY something or to have queried.
    said = list(at.error) + list(at.warning) + list(at.info)
    assert said or query_spy.RECORDED, (
        f"{view} rendered no message and issued no query for a tenant-less session. "
        "Silence is indistinguishable here from the view not having run, so this "
        "test would pass on a broken harness."
    )


def test_the_spy_sees_an_unscoped_read_when_there_is_one():
    """Non-vacuity. Without this, every assertion above is true of an empty list."""
    from tests import query_spy
    from src.dashboard.utils import get_db_connection

    query_spy.install()
    db = get_db_connection()
    try:
        db.fetch_query("SELECT 1 FROM s4a_song_timeline LIMIT 1")
    finally:
        db.close()
    assert query_spy.unscoped_tenant_reads(), (
        "the spy recorded nothing for a deliberately unscoped read on a tenant "
        "table — it is not wired to PostgresHandler, and the whole module passes "
        "on silence"
    )
