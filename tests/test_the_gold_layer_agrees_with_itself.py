"""Deux définitions or censées coïncider coïncident, sur les vraies données.

Type: Test
Uses: psycopg2, a live Postgres
Depends on: src/utils/gold_invariants.py, les vues or
Persists in: nothing

Why this exists
---------------
ADR-019 garantit qu'une métrique a **une seule définition**. C'est une propriété du
CODE. Que deux définitions censées coïncider coïncident est une propriété des
DONNÉES, et rien ne la vérifiait.

Mesuré en production le 2026-09-12 : `meta_insights_performance` et
`meta_insights_performance_day` répondent à la même question et divergeaient d'un
**facteur deux** — 6 165,65 € contre 3 087,82 € pour l'artiste 1, depuis des
semaines. Chaque côté était cohérent avec lui-même. Personne ne comparait.

`src/utils/metric_bounds.py` faisait déjà ça pour trois plateformes, à travers deux
portes Python. Il ne regardait ni Apple, ni Meta, ni le revenu, et il comparait des
portes et non des VUES : une vue or qui diverge de sa vue sœur lui est invisible.

Pourquoi ce test lit la BASE
-----------------------------
La question est « ces deux chemins rendent-ils le même nombre sur les données de ce
locataire ». Aucune lecture de code n'y répond : les deux définitions du spend Meta
étaient justes toutes les deux, et c'est la DONNÉE qui portait deux générations de
lignes. Même raison que `test_an_upsert_targets_an_index_that_exists.py`.

Mutation record — 2026-09-12 : en remettant la branche `soundcloud` de
`v_platform_totals` sur un `DISTINCT ON (track_id)` sans locataire (l'état d'avant la
migration 107), ce test resterait vert sur une base mono-locataire — il le DIT plutôt
que de le taire, et c'est pour ça que le compte de locataires comparés est asserté.
Vu rouge en faisant diverger `v_meta_spend_totals` d'un facteur deux dans une
transaction annulée : il nomme l'invariant, le locataire, les deux nombres et le
ratio.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _dsn() -> dict | None:
    if os.environ.get("DATABASE_URL"):
        return {"dsn": os.environ["DATABASE_URL"]}
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            pass
    except OSError:
        return None
    return {
        "host": _DB_HOST,
        "port": _DB_PORT,
        "dbname": os.environ.get("DATABASE_NAME", "spotify_etl"),
        "user": os.environ.get("DATABASE_USER", "postgres"),
        "password": os.environ.get("DATABASE_PASSWORD") or os.environ.get("DB_PASSWORD", ""),
    }


_CONN = _dsn()

pytestmark = pytest.mark.skipif(
    _CONN is None,
    reason=f"No Postgres on {_DB_HOST}:{_DB_PORT} — seule la donnée répond à cette question",
)


@pytest.fixture(scope="module")
def gi():
    sys.path.insert(0, str(_ROOT))
    from src.utils import gold_invariants
    return gold_invariants


@pytest.fixture(scope="module")
def cursor():
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.rollback()
        conn.close()


def _side(cur, sql: str) -> dict[int, float]:
    cur.execute(sql)
    return {int(t): float(v or 0) for t, v in cur.fetchall() if t is not None}


def test_every_gold_invariant_holds_on_the_real_data(gi, cursor) -> None:
    offenders, compared = [], 0
    for inv in gi.INVARIANTS:
        left = _side(cursor, inv.left_sql)
        right = _side(cursor, inv.right_sql)
        compared += len(set(left) | set(right))
        offenders += [gi.finding(inv, t, a, b) for t, a, b in gi.compare(left, right)]

    if compared == 0:
        pytest.skip("aucun locataire ne porte de données or — rien à réconcilier")

    assert not offenders, (
        "Deux définitions de la couche or censées rendre le même nombre n'en rendent\n"
        "pas le même. Ce n'est pas une dérive à surveiller : c'est un chiffre faux,\n"
        "aujourd'hui, sur une surface que quelqu'un lit.\n\n"
        + "\n\n".join(offenders))


def test_the_reconciliation_actually_compared_something(gi, cursor) -> None:
    """Non-vacuité : « zéro désaccord » sur zéro locataire est vrai et ne dit rien.

    Et le compte est par INVARIANT, pas global : un invariant dont les deux côtés
    sont vides passe sans bruit au milieu de six qui comparent, et c'est exactement
    comme ça qu'une vue supprimée cesserait d'être gardée.
    """
    empty = []
    for inv in gi.INVARIANTS:
        left = _side(cursor, inv.left_sql)
        right = _side(cursor, inv.right_sql)
        if not (set(left) | set(right)):
            empty.append(inv.name)

    cursor.execute("SELECT count(*) FROM v_platform_totals")
    has_gold = (cursor.fetchone() or [0])[0] > 0
    if not has_gold:
        pytest.skip("base sans données or")

    assert len(empty) < len(gi.INVARIANTS), (
        "AUCUN invariant n'a comparé quoi que ce soit alors que la couche or porte "
        "des lignes. Les requêtes ne rendent plus rien — le test est vert et ne "
        f"vérifie plus rien. Invariants vides : {empty}")


def test_every_invariant_names_the_defect_it_would_have_caught(gi) -> None:
    """Une règle sans son défaut se supprime au premier refactor qui la gêne.

    Ce dépôt a un précédent nommé : une leçon écrite en commentaire n'a gardé
    personne, et la classe est restée vivante dans six surfaces. Un invariant porte
    donc la mesure qui l'a fait naître, pas une justification générale.
    """
    thin = [inv.name for inv in gi.INVARIANTS if len(inv.why) < 120]
    assert not thin, (
        f"invariant(s) dont le `why` ne dit pas quel défaut il attrape : {thin}")
    names = [inv.name for inv in gi.INVARIANTS]
    assert len(names) == len(set(names)), f"noms d'invariants en double : {names}"
