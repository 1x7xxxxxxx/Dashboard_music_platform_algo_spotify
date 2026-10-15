"""The algo page still answers with no scored title, and says a failed read (R525, R570).

Type: Guard
Uses: src.dashboard.views.trigger_algo.router (show), src.dashboard.utils.navigation
      (goto, pop_goto_alias)
Depends on: live Postgres for the renders (skipped without)
Persists in: nothing

The defect (code-critic of R403/R405, 2026-10-12): `router.show()` returned right after
« Aucune donnée de timeline », so a tenant with no title saw an empty page. A raising
read was silenced the same way (`except: tracks = []`). And `goto(alias)` dropped the
alias: the in-app click landed on the top of the page, with no word of where the old
page went. R570 (2026-10-15) removed the budget and money sections the first two tests
used to look for: the page now reads `ml_song_predictions` for its picks, and the
« Une fois déclenché » section must still render without them.
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
    if "FROM ml_song_predictions" in query and "features_json" in query:
        return pd.DataFrame({"song": []})
    return _real(self, query, *a, **k)
PostgresHandler.fetch_df = _fetch_df
"""

_RAISING_READ = """
from src.database.postgres_handler import PostgresHandler
_real = PostgresHandler.fetch_df
def _fetch_df(self, query, *a, **k):
    if "FROM ml_song_predictions" in query and "features_json" in query:
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
def test_an_artist_without_a_scored_title_still_sees_the_page() -> None:
    at = _render(_NO_TITLE)        # a premium tenant whose catalogue read comes back empty
    headers = [h.value for h in at.header]
    assert section_label("catalogue") in headers, f"the page stops without a title: {headers}"
    assert any(b.key == "algo_entry_door" for b in at.button), "the page stops before its end"
    assert any("pas encore été noté" in i.value for i in at.info), "the empty state is not said"


@pytest.mark.skipif(not db_ready(), reason="renders the algo page against the live DB")
def test_a_raising_track_read_is_said_not_shown_as_no_data() -> None:
    at = _render(_RAISING_READ)
    errors = [e.value for e in at.error]
    assert any("Catalogue illisible" in e for e in errors), errors
    assert not [i for i in at.info if "pas encore été noté" in i.value], (
        "a failed read is still told as « no data »")
    assert any(b.key == "algo_entry_door" for b in at.button), "the page stops at the error"


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
