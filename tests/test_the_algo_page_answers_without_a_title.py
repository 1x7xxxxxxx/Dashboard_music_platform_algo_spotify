"""The algo page still shows its budget and money sections with no S4A title (R525).

Type: Guard
Uses: src.dashboard.views.trigger_algo.router (show), src.dashboard.utils.navigation
      (goto, pop_goto_alias)
Depends on: live Postgres for the renders (skipped without)
Persists in: nothing

The defect (code-critic of R403/R405, 2026-10-12): `router.show()` returned right after
« Aucune donnée de timeline » — so an artist with Meta spend and no S4A import, or anyone
following an old `meta_cpr_optimizer` link, saw an empty page although the CPR cards and
the money section need no title. A raising track read was silenced the same way
(`except: tracks = []`). And `goto(alias)` dropped the alias: the in-app click landed on
the top of the page, with no word of where the old page went.
"""
from __future__ import annotations

import os

import pytest

from src.dashboard.views.trigger_algo._sections import section_label
from tests.db_gate import db_ready
from tests.render_harness import TENANT_SCRIPT

_NO_TITLE = """
import pandas as pd
from src.database.postgres_handler import PostgresHandler
_real = PostgresHandler.fetch_df
def _fetch_df(self, query, *a, **k):
    if "FROM s4a_song_timeline" in query and "GROUP BY song" in query:
        return pd.DataFrame({"song": []})
    return _real(self, query, *a, **k)
PostgresHandler.fetch_df = _fetch_df
"""

_RAISING_READ = """
from src.database.postgres_handler import PostgresHandler
_real = PostgresHandler.fetch_df
def _fetch_df(self, query, *a, **k):
    if "FROM s4a_song_timeline" in query and "GROUP BY song" in query:
        raise RuntimeError("relation unreadable")
    return _real(self, query, *a, **k)
PostgresHandler.fetch_df = _fetch_df
"""


def _render(extra: str, artist_id: int = 1):
    from streamlit.testing.v1 import AppTest

    from src.database.postgres_handler import PostgresHandler

    script = TENANT_SCRIPT.format(root=os.getcwd(), view="trigger_algo", artist_id=artist_id)
    if extra:
        script = script.replace("from src.dashboard.views.", extra + "\nfrom src.dashboard.views.", 1)
    # AppTest shares `sys.modules` with this worker: the double posed by the script must
    # be taken back, or every later test on the worker reads through it.
    _original = PostgresHandler.fetch_df
    try:
        at = AppTest.from_string(script)
        at.run(timeout=300)
    finally:
        PostgresHandler.fetch_df = _original
    assert not at.exception, at.exception
    return at


@pytest.mark.skipif(not db_ready(), reason="renders the algo page against the live DB")
def test_an_artist_without_s4a_still_sees_the_budget_section() -> None:
    at = _render(_NO_TITLE)        # a premium tenant whose title read comes back empty
    headers = [h.value for h in at.header]
    assert section_label("budget") in headers, f"no budget section without a title: {headers}"


@pytest.mark.skipif(not db_ready(), reason="renders the algo page against the live DB")
def test_a_raising_track_read_is_said_not_shown_as_no_data() -> None:
    at = _render(_RAISING_READ)
    errors = [e.value for e in at.error]
    assert any("Lecture de vos titres impossible" in e for e in errors), errors
    assert not [w for w in at.warning if "Aucune donnée de timeline" in w.value], (
        "a failed read is still told as « no data »")
    assert section_label("budget") in [h.value for h in at.header]


def test_goto_keeps_the_alias_for_one_run(monkeypatch) -> None:
    from src.dashboard.utils import navigation as nav

    state: dict = {}
    monkeypatch.setattr(nav.st, "session_state", state)
    monkeypatch.setattr(nav.st, "rerun", lambda *a, **k: None)
    nav.goto("meta_cpr_optimizer")
    assert state[nav._PAGE_KEY] == "trigger_algo"
    assert nav.pop_goto_alias() == "meta_cpr_optimizer"
    assert nav.pop_goto_alias() is None, "the alias outlives the run it was set for"
    nav.goto("trigger_algo")
    assert nav.pop_goto_alias() is None, "a plain page key left an alias behind"
