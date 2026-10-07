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

R405 (V74, 2026-10-05) revised the first move: « Résultats réalisés » and « Le pari du
modèle » are SHARED by one module (`trigger_algo/_outcome_entry.render_outcomes`), drawn
on both pages — the S4A entry page is Free and the algo view Premium, and the outcome
entry must not sit behind the paywall. They come AFTER the coverage, which closes the
entry proper; « Fraîcheur » stays on the admin page only.
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


@pytest.fixture(scope="module")
def data() -> dict:
    """What artist 1 has in this database. The CI database is schema-only: without S4A
    titles both pages stop on their empty state, and there is no layout to judge."""
    from src.dashboard.utils import get_db_connection
    from src.dashboard.utils.s4a_entry_insight import load_entry_tracks
    from tests.conftest import pre_session_active_tenants

    db = get_db_connection()
    try:
        return {"tracks": bool(load_entry_tracks(db, 1)),
                "artists": bool(pre_session_active_tenants(db, limit=1))}
    finally:
        db.close()


def _need(data: dict, key: str) -> None:
    if not data[key]:
        pytest.skip(f"no {key} in this database — the page renders its empty state")


def _run(script: str):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script)
    at.run(timeout=180)
    assert not at.exception, at.exception
    return at


def _subheaders(at) -> list[str]:
    return [s.value for s in at.subheader]


def test_the_entry_page_is_signals_then_coverage(data: dict) -> None:
    _need(data, "tracks")
    at = _run(TENANT_SCRIPT.format(root=os.getcwd(), view="saisie_s4a", artist_id=1))
    heads = _subheaders(at)
    assert not at.tabs, f"the S4A entry page has tabs again: {[t.label for t in at.tabs]}"
    gone = [h for h in heads if _FRESH in h]
    assert not gone, f"a section moved by R376 is back on the entry page: {gone}"
    covered = next((i for i, h in enumerate(heads) if _COVERED in h), None)
    assert covered is not None, f"no coverage section: {heads}"
    at_ = [i for i, h in enumerate(heads) if _OUTCOMES in h]
    assert at_ and at_[0] > covered, (
        f"« {_OUTCOMES} » (shared, R405) is not after the coverage on the Free page: {heads}")
    # R442 (owner, 2026-10-07): the bet moved to the admin ML page.
    assert not any(_BET in h for h in heads), f"« {_BET} » is back on the entry page: {heads}"


def test_the_algo_view_carries_the_outcome_entry_but_not_the_bet(data: dict) -> None:
    _need(data, "tracks")
    at = _run(TENANT_SCRIPT.format(root=os.getcwd(), view="trigger_algo", artist_id=1))
    heads = _subheaders(at)
    assert any(_OUTCOMES in h for h in heads), f"« {_OUTCOMES} » is not on the algo view: {heads}"
    # R442: the bet is an admin reading now (ml_performance, « 🎲 Pari vs réalité »).
    assert not any(_BET in h for h in heads), f"« {_BET} » is back on the algo view: {heads}"


def test_the_admin_health_group_carries_the_entry_freshness(data: dict) -> None:
    _need(data, "artists")
    script = SCRIPT.format(root=os.getcwd(), view="admin").replace(
        "from src.dashboard.views.admin import show",
        'st.session_state["_admin_groupe"] = "sante"\n'
        'st.session_state["_admin_sous_sante"] = "s4a_fresh"\n'
        "from src.dashboard.views.admin import show")
    heads = _subheaders(_run(script))
    assert any(_FRESH in h and "S4A" in h for h in heads), (
        f"the S4A entry freshness is not on the admin page: {heads}")
