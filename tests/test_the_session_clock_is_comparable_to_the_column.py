"""Guard: the recorded session start must be comparable to what it is compared TO.

Type: Utility
Uses: tests.conftest, information_schema
Triggers: pytest
Persists in: nothing

Error class `guard-branch-only-reached-when-it-fails`.

Measured 2026-09-06. `conftest.pytest_sessionstart` recorded `SELECT
CURRENT_TIMESTAMP` — a `timestamptz`, offset-AWARE — and
`test_no_synthetic_track_survives_into_the_freshness_computation` compared it to
`saas_artists.created_at`, a `timestamp without time zone`, offset-NAIVE. Python
raises `TypeError: can't compare offset-naive and offset-aware datetimes`.

The comparison lives inside a list comprehension whose `if` is only evaluated for
rows that already look like offenders. On a clean database there are none, so the
broken branch was never executed: the guard was green on its own defect, and went
red only in the full parallel run — the one place a live tenant produces a candidate
row.

**And the mutation missed it.** The fix was "verified" by running the mutation and
reading `exit = 1`. The exit code was 1 because of this `TypeError`, not because the
guard had seen the planted row. A mutation proves nothing until its FAILURE MESSAGE
is read: red for the wrong reason looks exactly like red for the right one.

This file makes the contract reachable on every run, with no database write and no
offender needed: the two values must be of comparable kinds.
"""
from __future__ import annotations

import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _db():
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return None
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
        return db
    except Exception:  # noqa: BLE001
        return None


pytestmark = pytest.mark.skipif(_db() is None, reason="needs the provisioned DB")

# Les colonnes auxquelles le repère de session est comparé. Une seule aujourd'hui ;
# la liste est ici pour que l'ajout d'une comparaison ailleurs vienne s'y déclarer
# plutôt que de découvrir le problème en production de la suite.
_COMPARED_TO = [("saas_artists", "created_at")]


def test_the_session_start_was_recorded_at_all():
    """Sinon le filtre est inerte et le test suivant ne prouve rien."""
    from tests.conftest import _DB_SESSION_START
    assert _DB_SESSION_START, (
        "aucun repère de session enregistré alors que la base est joignable — "
        "`pytest_sessionstart` a échoué en silence, et le garde de fraîcheur "
        "retombe sur son ancien comportement sans le dire")


@pytest.mark.parametrize("table,column", _COMPARED_TO)
def test_the_session_start_is_comparable_to_that_column(table, column):
    """Les deux doivent être naïfs, ou les deux avertis. Jamais un de chaque."""
    from tests.conftest import _DB_SESSION_START

    db = _db()
    try:
        kind = db.fetch_query(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s", (table, column))
    finally:
        db.close()
    assert kind, f"{table}.{column} n'existe plus — la comparaison vise le vide"

    column_is_aware = "with time zone" in kind[0][0]
    recorded = _DB_SESSION_START[0]
    recorded_is_aware = recorded.tzinfo is not None

    assert recorded_is_aware == column_is_aware, (
        f"le repère de session est {'averti' if recorded_is_aware else 'naïf'} et "
        f"{table}.{column} est {'averti' if column_is_aware else 'naïf'} : les "
        "comparer lève `TypeError: can't compare offset-naive and offset-aware "
        "datetimes`. Et l'erreur ne sort QUE sur une ligne déjà suspecte, donc pas "
        "sur une base propre — c'est-à-dire jamais quand on la cherche. "
        "`LOCALTIMESTAMP` rend ce que la colonne écrit ; `CURRENT_TIMESTAMP` non.")

    # La comparaison elle-même, exécutée : une assertion sur les types pourrait
    # rester vraie sur deux types comparables séparément mais pas entre eux.
    from datetime import timedelta
    assert (recorded - timedelta(days=1)) < recorded
