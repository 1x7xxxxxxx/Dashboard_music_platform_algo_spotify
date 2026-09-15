"""Unit tests for view_session() — DB+artist guard context manager.

Behaviour parity with the inline boilerplate it replaces: resolved artist
yields (db, id); admin None yields (db, 1); non-admin None → st.error +
st.stop BEFORE the try (body never runs, db not closed — matches original).

Pourquoi on patche `streamlit.error` et non `src.dashboard.utils.st` (2026-09-16)
--------------------------------------------------------------------------------
Ces tests faisaient `patch("src.dashboard.utils.st", st)`. `unittest.mock.patch`
exige que l'attribut visé EXISTE déjà (pas de `create=True`) — c'était vrai tant
que la ligne 1 de ce module était `import streamlit as st`.

Le seam du 2026-09-16 l'a retirée : la porte de la base ne tire plus un framework
d'interface à l'import (**5,30 s** contre 0,19 s, payés par chaque processus pytest
et par l'image de l'API). `src.dashboard.utils` n'a donc plus d'attribut `st`, et
les quatre tests de ce fichier levaient `AttributeError` avant même leur corps —
une panne mécanique, sans rapport avec le comportement qu'ils vérifient.

On patche donc la SOURCE. `view_session()` fait `import streamlit as st` dans son
corps : son `st` est le module lui-même, et patcher `streamlit.error` /
`streamlit.stop` l'atteint. `st` reste ici le `MagicMock` sur lequel on assert.
La revue `code-critic` a nommé cette dépendance comme la condition bloquante du
seam — elle l'était.
"""
from unittest.mock import MagicMock, patch

import pytest

from src.dashboard.utils import view_session


class _Stop(Exception):
    """Stand-in for streamlit's st.stop() halt."""


def _run(artist_id, is_admin):
    db = MagicMock()
    st = MagicMock()
    st.stop.side_effect = _Stop
    with patch("src.dashboard.utils.get_db_connection", return_value=db), \
         patch("streamlit.error", st.error), \
         patch("streamlit.stop", st.stop), \
         patch("src.dashboard.auth.get_artist_id", return_value=artist_id), \
         patch("src.dashboard.auth.is_admin", return_value=is_admin):
        captured = {}
        try:
            with view_session() as (got_db, got_aid):
                captured["db"], captured["aid"] = got_db, got_aid
        except _Stop:
            captured["stopped"] = True
    return db, st, captured


def test_resolved_artist_yields_db_and_id():
    db, st, cap = _run(artist_id=7, is_admin=False)
    assert cap["db"] is db and cap["aid"] == 7
    db.close.assert_called_once()
    st.error.assert_not_called()


def test_admin_none_falls_back_to_one():
    db, st, cap = _run(artist_id=None, is_admin=True)
    assert cap["aid"] == 1
    db.close.assert_called_once()
    st.error.assert_not_called()


def test_non_admin_none_stops_before_body():
    db, st, cap = _run(artist_id=None, is_admin=False)
    assert cap.get("stopped") is True
    assert "aid" not in cap  # body never entered
    st.error.assert_called_once_with("Session invalide.")
    db.close.assert_not_called()  # st.stop() fired before the try


def test_db_close_runs_even_if_body_raises():
    db = MagicMock()
    st = MagicMock()
    with patch("src.dashboard.utils.get_db_connection", return_value=db), \
         patch("streamlit.error", st.error), \
         patch("streamlit.stop", st.stop), \
         patch("src.dashboard.auth.get_artist_id", return_value=3), \
         patch("src.dashboard.auth.is_admin", return_value=False):
        with pytest.raises(ValueError):
            with view_session() as (_db, _aid):
                raise ValueError("boom")
    db.close.assert_called_once()
