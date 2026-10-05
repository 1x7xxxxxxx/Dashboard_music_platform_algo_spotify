"""The S4A entry page has no tabs; each section it lost is found where it went (R376).

Type: Guard
Uses: tests/render_harness.py (SCRIPT, TENANT_SCRIPT), streamlit AppTest
Depends on: live Postgres with artist 1's S4A data (skipped without it)
Persists in: nothing

Owner's screen review, 2026-10-05: « Signaux du mois » stays, « Titres couverts par la
saisie » at its end; « Résultats réalisés » and « Le pari du modèle, et ce qui est
arrivé » go to the algo view, beside the prediction they judge; « Fraîcheur des
saisies » goes to the admin page. A move is two properties — gone from here AND present
there — so each destination is rendered, not only the source.
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import db_ready
from tests.render_harness import SCRIPT, TENANT_SCRIPT

pytestmark = pytest.mark.skipif(not db_ready(), reason="renders three views against the live DB")

_BET = "Le pari du modèle"
_OUTCOMES = "Streams algorithmiques réalisés"
_FRESH = "Fraîcheur"
_COVERED = "Titres couverts par la saisie"


def _run(script: str):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script)
    at.run(timeout=180)
    assert not at.exception, at.exception
    return at


def _subheaders(at) -> list[str]:
    return [s.value for s in at.subheader]


def test_the_entry_page_is_signals_then_coverage() -> None:
    at = _run(TENANT_SCRIPT.format(root=os.getcwd(), view="saisie_s4a", artist_id=1))
    heads = _subheaders(at)
    assert not at.tabs, f"the S4A entry page has tabs again: {[t.label for t in at.tabs]}"
    gone = [h for h in heads if any(k in h for k in (_BET, _OUTCOMES, _FRESH))]
    assert not gone, f"a section moved by R376 is back on the entry page: {gone}"
    assert heads and _COVERED in heads[-1], f"coverage is not the last section: {heads}"


def test_the_algo_view_carries_the_bet_and_the_outcome_entry() -> None:
    at = _run(TENANT_SCRIPT.format(root=os.getcwd(), view="trigger_algo", artist_id=1))
    heads = _subheaders(at)
    for want in (_BET, _OUTCOMES):
        assert any(want in h for h in heads), f"« {want} » is not on the algo view: {heads}"


def test_the_admin_health_group_carries_the_entry_freshness() -> None:
    script = SCRIPT.format(root=os.getcwd(), view="admin").replace(
        "from src.dashboard.views.admin import show",
        'st.session_state["_admin_groupe"] = "sante"\n'
        'st.session_state["_admin_sous_sante"] = "s4a_fresh"\n'
        "from src.dashboard.views.admin import show")
    heads = _subheaders(_run(script))
    assert any(_FRESH in h and "S4A" in h for h in heads), (
        f"the S4A entry freshness is not on the admin page: {heads}")
