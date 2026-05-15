"""Unit tests for view_session() — DB+artist guard context manager.

Behaviour parity with the inline boilerplate it replaces: resolved artist
yields (db, id); admin None yields (db, 1); non-admin None → st.error +
st.stop BEFORE the try (body never runs, db not closed — matches original).
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
         patch("src.dashboard.utils.st", st), \
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
         patch("src.dashboard.utils.st", st), \
         patch("src.dashboard.auth.get_artist_id", return_value=3), \
         patch("src.dashboard.auth.is_admin", return_value=False):
        with pytest.raises(ValueError):
            with view_session() as (_db, _aid):
                raise ValueError("boom")
    db.close.assert_called_once()
