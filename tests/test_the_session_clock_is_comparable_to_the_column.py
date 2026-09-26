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


_needs_db = pytest.mark.skipif(_db() is None, reason="needs the provisioned DB")

# Les colonnes auxquelles le repère de session est comparé. Une seule aujourd'hui ;
# la liste est ici pour que l'ajout d'une comparaison ailleurs vienne s'y déclarer
# plutôt que de découvrir le problème en production de la suite.
_COMPARED_TO = [("saas_artists", "created_at")]


def comparable(recorded, data_type: str) -> bool:
    """Can a Python datetime be compared to a column of this SQL type? Pure."""
    return (recorded.tzinfo is not None) == ("with time zone" in data_type)


@_needs_db
def test_the_session_start_was_recorded_at_all():
    """Sinon le filtre est inerte et le test suivant ne prouve rien."""
    from tests.conftest import _DB_SESSION_START
    assert _DB_SESSION_START, (
        "aucun repère de session enregistré alors que la base est joignable — "
        "`pytest_sessionstart` a échoué en silence, et le garde de fraîcheur "
        "retombe sur son ancien comportement sans le dire")


@_needs_db
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

    assert comparable(recorded, kind[0][0]), (
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


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity, without a database: the 2026-09-06 pair — `CURRENT_TIMESTAMP`
    (aware) against `saas_artists.created_at` (naive) — is refused, and it is refused
    because the comparison REALLY raises; the matching pairs are accepted."""
    from datetime import datetime, timezone

    aware, naive = datetime(2026, 9, 6, tzinfo=timezone.utc), datetime(2026, 9, 6)
    assert not comparable(aware, "timestamp without time zone")
    with pytest.raises(TypeError):
        _ = aware < naive                      # the premise: the defect is a crash
    assert comparable(naive, "timestamp without time zone")
    assert comparable(aware, "timestamp with time zone")


# ── Le repère est UNIQUE pour toute l'exécution, pas un par worker ───────────
# Mesuré le 2026-09-06, et c'est la seconde cause du même rouge. Chaque worker xdist
# lisait sa propre heure de départ. Ils ne démarrent pas ensemble : un locataire créé
# par le worker A à T est ANTÉRIEUR au `sessionstart` du worker B démarré à T+2 s,
# donc le filtre « créé pendant la session » ne l'excluait pas chez B, qui le
# dénonçait comme une ligne fabriquée survivante pendant qu'un test voisin s'en
# servait.
#
# Le décalage se compte en secondes et n'existe QUE dans l'exécution parallèle : le
# reproduire par le temps serait une signature instable. On garde donc le MÉCANISME —
# le contrôleur fixe l'instant et le passe dans `workerinput`, le worker le préfère
# au sien — qui est vrai ou faux sans dépendre d'un chronomètre.


def _conftest_tree():
    import ast
    from pathlib import Path as _P
    return ast.parse((_P(__file__).parent / "conftest.py").read_text(encoding="utf-8"))


def reference_point_defects(tree) -> set[str]:
    """What stops the controller's reference point from reaching every worker. Pure.

    `no-configure-node` / `node-sends-nothing`: the controller never hands it over.
    `no-sessionstart` / `worker-ignores-it`: the worker never reads it.
    `own-clock-first`: the worker reads its own clock before the shared one.
    """
    import ast

    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    out = set()
    node = fns.get("pytest_configure_node")
    if node is None:
        out.add("no-configure-node")
    elif "workerinput" not in ast.unparse(node):
        out.add("node-sends-nothing")
    start = fns.get("pytest_sessionstart")
    if start is None:
        out.add("no-sessionstart")
        return out
    if "workerinput" not in ast.unparse(start):
        out.add("worker-ignores-it")
        return out
    # Order of EVALUATION, not of text: `_read_db_clock() or wi.get(...)` names
    # `workerinput` first and still reads its own clock first.
    def first(pred):
        calls = [(c.lineno, c.col_offset) for c in ast.walk(start)
                 if isinstance(c, ast.Call) and pred(c.func)]
        return min(calls) if calls else None
    own = first(lambda f: getattr(f, "id", "") == "_read_db_clock")
    shared = first(lambda f: isinstance(f, ast.Attribute) and f.attr == "get")
    if own is not None and (shared is None or own < shared):
        out.add("own-clock-first")
    return out


def test_the_reference_point_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity, class `per-worker-reference-point-for-shared-state`: the conftest
    of before 2026-09-06 — each worker reads its own clock — is named, so is a worker
    that reads its own clock BEFORE the shared one; the fixed shape is not."""
    import ast

    old = ast.parse("def pytest_sessionstart(session):\n"
                    "    session.config._t0 = _read_db_clock()\n")
    assert reference_point_defects(old) == {"no-configure-node", "worker-ignores-it"}
    fixed = ("def pytest_configure_node(node):\n"
             "    node.workerinput['t0'] = _T0\n"
             "def pytest_sessionstart(session):\n"
             "    wi = getattr(session.config, 'workerinput', {})\n"
             "    t0 = wi.get('t0') or _read_db_clock()\n")
    assert reference_point_defects(ast.parse(fixed)) == set()
    inverted = fixed.replace("wi.get('t0') or _read_db_clock()",
                             "_read_db_clock() or wi.get('t0')")
    assert reference_point_defects(ast.parse(inverted)) == {"own-clock-first"}
    silent = fixed.replace("node.workerinput['t0'] = _T0", "node.log('started')")
    assert reference_point_defects(ast.parse(silent)) == {"node-sends-nothing"}


def test_the_controller_hands_the_reference_point_to_every_worker():
    """`pytest_configure_node` ne tourne que sur le contrôleur — c'est le point."""
    found = reference_point_defects(_conftest_tree()) & {"no-configure-node",
                                                          "node-sends-nothing"}
    assert not found, (
        f"{found} : `pytest_configure_node` manque ou ne pose rien dans `workerinput`. "
        "Chaque worker relit alors l'horloge à son propre démarrage, et un locataire "
        "créé par un worker voisin quelques secondes plus tôt échappe au filtre "
        "« créé pendant la session ».")


def test_the_worker_prefers_the_shared_reference_point_over_its_own():
    """Le poser ne suffit pas : encore faut-il le préférer, et le lire AVANT de
    fabriquer le sien."""
    found = reference_point_defects(_conftest_tree()) & {
        "no-sessionstart", "worker-ignores-it", "own-clock-first"}
    assert not found, (
        f"{found} : le repère du contrôleur est envoyé et ignoré, ou lu après que le "
        "worker a lu sa propre horloge — le défaut d'origine avec une étape de plus.")
