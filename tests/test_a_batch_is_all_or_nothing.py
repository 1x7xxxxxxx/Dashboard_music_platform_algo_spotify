"""Un lot s'applique en entier ou pas du tout.

Type: Test
Uses: pytest, ast, live Postgres (pour la preuve de comportement)
Depends on: src/database/postgres_handler.py
Persists in: nothing (nettoie ses propres lignes)

Ce qui a été mesuré (2026-09-10)
--------------------------------
La connexion est en `autocommit = True` — le bon défaut pour une écriture isolée.
Sur un LOT, il produisait deux effets :

* `insert_many` appelait `executemany`, donc **une transaction par ligne** : 1 500
  titres pour un locataire faisaient 1 500 transactions, chacune avec son fsync ;
* et surtout, un échec à la ligne 501 laissait **500 lignes committées**. La collecte
  était appliquée à moitié, et rien en base ne permettait de savoir laquelle des deux
  moitiés on regardait.

La lenteur est le symptôme visible ; l'état partiel indiscernable d'un état complet
est le défaut. C'est la même famille que « le non-mesuré affiché comme zéro » : une
donnée fausse qui ne ressemble pas à une erreur.

Mesuré après correctif : 1 500 lignes en 118 ms, et **0 ligne committée** quand la
501ᵉ viole une contrainte.

`execute_values` (une seule instruction pour tout le lot, 67 ms mesurés) a été essayé
et écarté : il exige un vrai curseur psycopg2 pour rendre les identifiants, ce qui
rend `test_a_bulk_write_sees_every_column` inexécutable. Ce garde tient une classe
déjà payée — `bulk-write-reads-only-the-first-row` — et on ne désarme pas un garde
pour gagner 50 ms sur un lot nocturne. Le défaut à retirer était la transaction par
ligne ; il l'est.
"""
from __future__ import annotations

import ast
from functools import lru_cache
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

_SRC_PATH = Path(__file__).resolve().parents[1] / "src" / "database" / "postgres_handler.py"


@lru_cache(maxsize=1)
def _tree() -> ast.Module:
    """Lu à l'APPEL, pas à l'import : un fichier de test doit rester collectable même
    quand ce qu'il surveille a disparu, sinon sa disparition casse la collecte de toute
    la suite au lieu de rougir un seul test."""
    return ast.parse(_SRC_PATH.read_text(encoding="utf-8"))


def _method(name: str) -> ast.FunctionDef:
    for cls in (n for n in ast.walk(_tree()) if isinstance(n, ast.ClassDef)):
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and fn.name == name:
                return fn
    raise AssertionError(f"{name} introuvable dans postgres_handler")


def _guards_with_atomic(fn: ast.FunctionDef) -> bool:
    """Le lot est-il exécuté DANS un `with self._atomic()` ?"""
    for node in ast.walk(fn):
        if not isinstance(node, ast.With):
            continue
        ctx = node.items[0].context_expr
        if (isinstance(ctx, ast.Call) and isinstance(ctx.func, ast.Attribute)
                and ctx.func.attr == "_atomic"):
            body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
            if "execute_values" in body or "execute_batch" in body:
                return True
    return False


@pytest.mark.parametrize("method", ["insert_many", "upsert_many"])
def test_the_batch_runs_inside_one_transaction(method) -> None:
    assert _guards_with_atomic(_method(method)), (
        f"{method} envoie son lot hors de `self._atomic()` : avec `autocommit = "
        "True`, un échec au milieu laisse la première moitié committée et la "
        "seconde dehors, sans que rien ne le signale")


def test_insert_many_no_longer_sends_one_statement_per_row() -> None:
    """`executemany` = un aller-retour ET une transaction par ligne."""
    # Collecter les DEUX formes d'appel : `self.cursor.executemany(...)` (Attribute) et
    # `execute_batch(...)` (Name, fonction importée). Ne lire que `.attr` rendait ce
    # prédicat aveugle à l'implémentation réelle — il a été rouge sur du code correct.
    calls = {getattr(n.func, "attr", None) or getattr(n.func, "id", None)
             for n in ast.walk(_method("insert_many")) if isinstance(n, ast.Call)}
    assert "executemany" not in calls, (
        "insert_many est revenu à `executemany` : 1 500 titres = 1 500 transactions")
    assert "execute_batch" in calls or "execute_values" in calls, (
        "insert_many n'envoie plus son lot par un helper de psycopg2 — le prédicat "
        "ci-dessus serait alors satisfait par une implémentation qui n'écrit rien")


def test_the_atomic_context_restores_what_it_changed() -> None:
    """Suspendre l'autocommit sans le rendre casserait toutes les écritures suivantes."""
    fn = _method("_atomic")
    finallys = [n for n in ast.walk(fn) if isinstance(n, ast.Try) and n.finalbody]
    assert finallys, (
        "`_atomic` ne restaure pas l'autocommit dans un `finally` : une exception "
        "laisserait la connexion en transaction ouverte pour tout le reste de la "
        "session, et chaque écriture suivante attendrait un commit que personne "
        "n'écrit")
    restored = any("autocommit" in ast.dump(stmt)
                   for t in finallys for stmt in t.finalbody)
    assert restored, "le `finally` de `_atomic` ne remet pas l'autocommit"


# ── La preuve de comportement, sur une base vivante ──────────────────────────
def _db_ready() -> bool:
    if os.environ.get("DATABASE_URL"):
        return True
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=1.5):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _db_ready(), reason="pas de Postgres joignable sur 5433")
def test_a_failing_row_leaves_none_of_its_batch_behind() -> None:
    from src.database.postgres_handler import PostgresHandler

    tag = "test_batch_atomicity"
    db = PostgresHandler.from_env_or_config()
    now = datetime.now(timezone.utc)

    def count() -> int:
        return db.fetch_query(
            "SELECT count(*) FROM etl_run_log WHERE dag_id = %s", (tag,))[0][0]

    def clean() -> None:
        db.execute_query("DELETE FROM etl_run_log WHERE dag_id = %s", (tag,))

    def row(i: int, artist_id=1) -> dict:
        return {"dag_id": tag, "artist_id": artist_id, "platform": "spotify",
                "status": "success", "started_at": now, "ended_at": now,
                "rows_inserted": i}

    try:
        clean()
        # `artist_id` est NOT NULL : la 501ᵉ ligne fait lever l'instruction.
        batch = ([row(i) for i in range(500)]
                 + [row(999, artist_id=None)]
                 + [row(i) for i in range(500, 1000)])
        with pytest.raises(Exception):
            db.insert_many("etl_run_log", batch)
        assert count() == 0, (
            f"{count()} lignes d'un lot refusé sont restées en base : la collecte "
            "est appliquée à moitié, et rien ne distingue cet état d'un état complet")
        assert db.conn.autocommit is True, (
            "l'autocommit n'a pas été restauré après l'échec — toute écriture "
            "ultérieure de cette connexion resterait non validée")

        db.insert_many("etl_run_log", [row(i) for i in range(50)])
        assert count() == 50, "un lot valide doit s'appliquer en entier"
    finally:
        clean()
        db.close()
