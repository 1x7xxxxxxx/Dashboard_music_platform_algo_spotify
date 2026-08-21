"""The one write path on hypeddit, covered directly because no click can reach it.

Installed 2026-08-21, as the prerequisite to the last view in roadmap item R9.

`hypeddit.add_campaign_stats(db, ...)` writes two tables from a form submit. Nothing
covered it: `test_views_render_smoke` renders `show()` without pressing anything,
and `AppTest` cannot re-run this page at all — it renders a single-mode
`st.segmented_control` (via `smart_period_filter`), and the harness iterates that
widget's scalar value as if it were a sequence of options. So the click route is
closed by a Streamlit testing limitation, not by choice.

Calling the function directly is the better test anyway: a click asserts "nothing
raised", while this asserts what actually matters — that the rows land under the
tenant who submitted the form, and that a second submit for the same day updates
instead of duplicating.

That second property is not cosmetic. `hypeddit_daily_stats` is keyed on
`(artist_id, campaign_name, date)`, and a form a user re-submits after a typo must
correct the day, not add a second row for it.
"""
from __future__ import annotations

import datetime as _dt
import uuid

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()


@pytest.fixture
def db():
    from src.dashboard.utils import get_db_connection

    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture
def tenant(db):
    """A tenant of our own, removed afterwards with everything it wrote."""
    suffix = uuid.uuid4().hex[:10]
    artist_id = db.fetch_query(
        "INSERT INTO saas_artists (name, slug, tier) VALUES (%s, %s, %s) RETURNING id",
        (f"Hyp {suffix}", f"hyp-{suffix}", "free"),
    )[0][0]
    yield {"artist_id": artist_id, "campaign": f"camp-{suffix}"}
    db.execute_query("DELETE FROM hypeddit_daily_stats WHERE artist_id = %s", (artist_id,))
    db.execute_query("DELETE FROM hypeddit_campaigns WHERE artist_id = %s", (artist_id,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


@pytest.fixture
def as_tenant(monkeypatch, tenant):
    """Answer `get_artist_id()` as this tenant, without a Streamlit session."""
    from src.dashboard.views import hypeddit

    monkeypatch.setattr(hypeddit, "get_artist_id", lambda: tenant["artist_id"])
    monkeypatch.setattr(hypeddit, "is_admin", lambda: False)
    return tenant


def _rows(db, artist_id: int, campaign: str):
    return db.fetch_query(
        "SELECT date, visits, clicks FROM hypeddit_daily_stats "
        "WHERE artist_id = %s AND campaign_name = %s ORDER BY date",
        (artist_id, campaign),
    )


def test_a_submit_writes_under_the_submitting_tenant(db, as_tenant):
    from src.dashboard.views.hypeddit import add_campaign_stats

    day = _dt.date.today()
    ok, msg = add_campaign_stats(db, as_tenant["campaign"], day, 120, 30)
    assert ok, msg

    rows = _rows(db, as_tenant["artist_id"], as_tenant["campaign"])
    assert len(rows) == 1, f"expected one row, got {rows}"
    assert (rows[0][1], rows[0][2]) == (120, 30)

    # And the campaign row it depends on exists, under the same tenant.
    camp = db.fetch_query(
        "SELECT count(*) FROM hypeddit_campaigns WHERE artist_id = %s AND campaign_name = %s",
        (as_tenant["artist_id"], as_tenant["campaign"]),
    )
    assert camp[0][0] == 1


def test_resubmitting_the_same_day_corrects_it_instead_of_duplicating(db, as_tenant):
    """A user fixing a typo must not end the day with two conflicting rows."""
    from src.dashboard.views.hypeddit import add_campaign_stats

    day = _dt.date.today()
    add_campaign_stats(db, as_tenant["campaign"], day, 120, 30)
    ok, msg = add_campaign_stats(db, as_tenant["campaign"], day, 121, 31)
    assert ok, msg

    rows = _rows(db, as_tenant["artist_id"], as_tenant["campaign"])
    assert len(rows) == 1, (
        f"{len(rows)} rows for one campaign-day — the upsert key "
        "(artist_id, campaign_name, date) is not doing its job: {rows}"
    )
    assert (rows[0][1], rows[0][2]) == (121, 31), "the correction did not land"


def test_nothing_is_written_for_a_session_with_no_tenant(db, monkeypatch, tenant):
    """No tenant and not admin ⇒ refuse, rather than pick one.

    The class this repo spent two sessions removing: an unreadable identity must
    never become somebody else's.
    """
    from src.dashboard.views import hypeddit

    monkeypatch.setattr(hypeddit, "get_artist_id", lambda: None)
    monkeypatch.setattr(hypeddit, "is_admin", lambda: False)

    ok, msg = hypeddit.add_campaign_stats(db, tenant["campaign"], _dt.date.today(), 5, 1)
    assert ok is False
    assert "session" in msg.lower()

    orphans = db.fetch_query(
        "SELECT count(*) FROM hypeddit_daily_stats WHERE campaign_name = %s",
        (tenant["campaign"],),
    )
    assert orphans[0][0] == 0, "a session with no tenant still wrote a row"
