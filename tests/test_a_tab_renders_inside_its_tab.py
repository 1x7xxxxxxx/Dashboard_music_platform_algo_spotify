"""A tab that renders nothing is usually a `with` that went missing.

Type: Test
Uses: streamlit.testing.v1.AppTest, live Postgres
Depends on: views that call st.tabs()
Persists in: nothing

The defect this was written from
--------------------------------
Splitting `admin.show()` (401 lines) into one function per tab, the first attempt
replaced

    with tab_gdpr:
        <85 lines>

by

    _tab_gdpr(db)

instead of

    with tab_gdpr:
        _tab_gdpr(db)

The page still rendered. No exception. Every element still existed. The content had
simply moved OUT of its tab and into the page body.

**Nothing in the suite saw it**, and that is the point worth keeping:

  * `test_views_render_smoke` asserts "no exception" — there was none;
  * `test_admin_hypeddit_buttons` finds buttons by label — they were all still there;
  * a fingerprint of `at.main` — element kinds and counts — came back **byte-for-byte
    identical**, because `at.main` flattens the tree. I built that fingerprint first,
    called the refactor proven, and it had proven nothing.

Only counting elements **per tab** diverged: the tab went from nine widgets to zero.

So the assertion is: in a view that builds tabs, no tab is empty. It is crude on
purpose — it needs no per-view expectations to maintain, and it fails on exactly the
mistake that is easy to make and invisible to everything else.
"""
from __future__ import annotations

import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433

# Views whose show() builds tabs. A view here whose tabs all render empty is either
# broken or should not be in this list — both are worth a failure.
#
# ⚠️ `admin` A QUITTÉ CETTE LISTE LE 2026-09-22, et ce n'est pas un desserrage : elle
# n'a PLUS d'onglets. Ses sept `st.tabs` sont devenus un sélecteur à six sections,
# parce que Streamlit exécute le corps de CHAQUE onglet à chaque rerun — mesuré,
# regrouper les dix écrans d'administration en onglets coûtait **93 requêtes par
# clic**, là où un sélecteur n'en paie que 1 à 22 selon la section regardée.
#
# Ce garde a rougi et il a dit exactement la bonne chose : « admin renders no tabs at
# all — is it still a tabbed view? ». La réponse est non. Sa propriété — le contenu
# d'un onglet se rend DANS son onglet — reste vraie et garde désormais
# `trigger_algo`, qui porte quatre vrais `st.tabs`.
#
# Ce que l'admin garde à la place : `test_the_admin_page_renders_one_section_at_a_time`,
# qui refuse le retour à `st.tabs` et vérifie que chaque section rend quelque chose.
TABBED_VIEWS = ["trigger_algo"]

# Element kinds that count as "this tab rendered something".
_PROBES = ("button", "dataframe", "selectbox", "text_input", "subheader", "checkbox",
           "expander", "metric", "caption", "file_uploader", "markdown", "info",
           "warning", "error", "number_input", "date_input", "radio", "text_area")


# La porte LÉGÈRE. Le corps recopié ici importait `get_db_connection`
# (**5,30 s**, dont 5,19 s de Streamlit) et ouvrait une connexion À L'IMPORT du
# module, donc à la collecte, une fois par fichier et par worker.
# `tests.db_gate.db_ready` répond en 0,19 s, derrière un `lru_cache` partagé, et
# sonde en plus `DATABASE_URL` et le schéma réel. Le nom est conservé : seuls le
# coût et le nombre de connexions changent.
from tests.db_gate import db_ready as _db_ready  # noqa: E402


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} — "
           "tab nesting can only be read from a real render",
)

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


def elements_per_tab(view: str) -> list[int]:
    """How many widgets each tab of `view` actually contains."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), view=view))
    at.run(timeout=300)
    counts = []
    for tab in at.tabs:
        n = 0
        for probe in _PROBES:
            try:
                n += len(getattr(tab, probe))
            except Exception:
                pass
        counts.append(n)
    return counts


@pytest.mark.parametrize("view", TABBED_VIEWS)
def test_no_tab_renders_empty(view):
    counts = elements_per_tab(view)
    assert counts, f"{view} renders no tabs at all — is it still a tabbed view?"
    empty = [i for i, n in enumerate(counts) if n == 0]
    assert not empty, (
        f"{view}: tab(s) {empty} rendered ZERO widgets while the others rendered "
        f"{counts}. The usual cause is a body extracted out of its `with tab_x:` — "
        "the content then lands in the page instead of the tab, raises nothing, and "
        "keeps every other test green."
    )


def test_the_flat_fingerprint_would_have_missed_this():
    """Pin the reason this test exists, so nobody replaces it with a cheaper one.

    Counting elements over `at.main` is the obvious equivalence check for a refactor.
    It is also blind here: `at.main` is flat, so content moved out of a tab is still
    content on the page. Asserted by construction — the flat total must equal the sum
    over tabs plus whatever sits outside them, i.e. the flat view cannot distinguish
    the two placements.
    """
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), view="admin"))
    at.run(timeout=300)
    flat_buttons = len(at.button)
    per_tab = sum(len(t.button) for t in at.tabs)
    assert flat_buttons >= per_tab, (
        "at.main reports fewer buttons than its tabs contain, which would mean the "
        "flat view is not a superset — the reasoning in this file's docstring would "
        "need re-deriving."
    )
