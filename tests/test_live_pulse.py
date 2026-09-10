"""Unit tests — live_pulse helpers (Brick 32).

Mocks the PostgresHandler at the call interface (execute_query / fetch_query).
Validates SQL strings, parameter passing, fire-and-forget semantics, and the
returned tuple shape. Integration with a real DB is covered by the manual
verification steps in the brick plan.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import psycopg2
import pytest

from src.dashboard.utils.live_pulse import (
    _PULSE_TTL_S, _pulse_counts, bump_heartbeat, get_live_pulse)


@pytest.fixture(autouse=True)
def _no_pulse_cache():
    """Le pouls est caché depuis le 2026-09-10 — sans purge, un test empoisonne le suivant.

    `_pulse_counts` porte un `@st.cache_data(ttl=30)`. Trois tests de ce fichier
    appellent `get_live_pulse` avec des doublures différentes dans la même fenêtre :
    le premier remplit le cache, les suivants n'atteignent jamais leur propre
    doublure et lisent `call_args is None`. Le cache est la bonne décision (voir le
    module) ; ce qui manquait était de le vider entre deux tests.
    """
    _pulse_counts.clear()
    yield
    _pulse_counts.clear()


class TestBumpHeartbeat:
    def test_executes_upsert_with_artist_id(self):
        db = MagicMock()
        bump_heartbeat(db, artist_id=42)
        db.execute_query.assert_called_once()
        sql, params = db.execute_query.call_args[0]
        assert "INSERT INTO active_sessions" in sql
        assert "ON CONFLICT (artist_id) DO UPDATE" in sql
        assert "last_heartbeat = NOW()" in sql
        assert params == (42,)

    def test_swallows_psycopg2_error(self):
        db = MagicMock()
        db.execute_query.side_effect = psycopg2.OperationalError("connection closed")
        # Must not raise — fire-and-forget contract.
        bump_heartbeat(db, artist_id=1)

    def test_does_not_swallow_generic_exception(self):
        # Only psycopg2.Error is caught; programmer errors must surface.
        db = MagicMock()
        db.execute_query.side_effect = ValueError("bad call")
        with pytest.raises(ValueError):
            bump_heartbeat(db, artist_id=1)


class TestGetLivePulse:
    def test_returns_live_and_registered_counts(self):
        db = MagicMock()
        db.fetch_query.return_value = [(7, 123)]
        live, registered = get_live_pulse(db, ttl_minutes=5)
        assert live == 7
        assert registered == 123

    def test_returns_zero_zero_when_query_empty(self):
        db = MagicMock()
        db.fetch_query.return_value = []
        assert get_live_pulse(db) == (0, 0)

    def test_cutoff_param_reflects_ttl_minutes(self):
        db = MagicMock()
        db.fetch_query.return_value = [(0, 0)]
        before = datetime.now(timezone.utc) - timedelta(minutes=10)
        get_live_pulse(db, ttl_minutes=10)
        after = datetime.now(timezone.utc) - timedelta(minutes=10)
        sql, params = db.fetch_query.call_args[0]
        (cutoff,) = params
        # Cutoff must be UTC-aware and within the 10-min window around the call.
        #
        # La tolérance suit `_PULSE_TTL_S`, pas une constante à part : la borne est
        # ARRONDIE à la fenêtre de cache, délibérément — sans cet arrondi chaque rerun
        # produit une clé neuve et le cache n'a jamais un seul succès. L'arrondi ne
        # peut que reculer le `cutoff`, jamais l'avancer, d'où l'asymétrie ci-dessous.
        assert cutoff.tzinfo is not None
        assert (before - timedelta(seconds=_PULSE_TTL_S)
                <= cutoff <= after + timedelta(seconds=2))
        assert "active = TRUE" in sql
        assert "last_heartbeat > %s" in sql

    def test_default_ttl_is_five_minutes(self):
        db = MagicMock()
        db.fetch_query.return_value = [(0, 0)]
        get_live_pulse(db)  # default
        (cutoff,) = db.fetch_query.call_args[0][1]
        expected = datetime.now(timezone.utc) - timedelta(minutes=5)
        # Idem : l'arrondi ne peut que RECULER la borne, d'au plus une fenêtre de
        # cache. Une borne en AVANCE, elle, resterait un défaut — elle exclurait des
        # sessions vivantes.
        delta = (expected - cutoff).total_seconds()
        assert -2 < delta < _PULSE_TTL_S + 2, delta
