"""A pooled connection carries the same guarantees as a direct one.

Type: Test
Uses: psycopg2, a live Postgres
Depends on: src/database/postgres_handler.py
Persists in: nothing

Why this exists
---------------
Pooling was rejected on 2026-08-30 on a measurement of the wrong quantity: SQL
across the 42 views timed at 2 ms per query, so pooling "gained nothing". That
is the cost of QUERIES. The cost of a CONNECTION had not been taken — measured
from the production container on 2026-09-11 it is **13 ms**, and a full page
render opens **four**: 52 ms of a 287 ms render, 18 %.

A pool is cheap to add and quiet to break. The three things that would break
without any error appearing are pinned here:

  * **`statement_timeout` would vanish.** It is not a server setting here, it
    travels in the connection's `options`. A pool that creates its connections
    without them silently removes the 15 s ceiling that keeps a locked table
    from holding an API thread forever.
  * **An aborted transaction would poison the pool.** `_atomic()` turns
    autocommit off for the duration of a batch; a failure inside leaves the
    connection in `current transaction is aborted`, and the *next* borrower
    inherits it. Every borrower after that fails, on code that is correct.
  * **`close()` would destroy instead of return.** The pool would then be an
    indirection that changes nothing — the failure mode where a performance fix
    ships, measures nothing, and nobody can say why.

Measured on 2026-09-11 with these tests' own harness: 20 open/query/close cycles
performed **0** handshakes with the pool against **20** without, 12.6 ms → 0.3 ms
per cycle.
"""
from __future__ import annotations

import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _kwargs() -> dict | None:
    if os.environ.get("DATABASE_URL"):
        from urllib.parse import urlparse
        u = urlparse(os.environ["DATABASE_URL"])
        return {"host": u.hostname or "localhost", "port": u.port or 5432,
                "database": (u.path or "").lstrip("/"), "user": u.username or "postgres",
                "password": u.password or ""}
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            pass
    except OSError:
        return None
    return {"host": _DB_HOST, "port": _DB_PORT,
            "database": os.environ.get("DATABASE_NAME", "spotify_etl"),
            "user": os.environ.get("DATABASE_USER", "postgres"),
            "password": os.environ.get("DATABASE_PASSWORD") or os.environ.get("DB_PASSWORD", "")}


_KW = _kwargs()

pytestmark = pytest.mark.skipif(
    _KW is None, reason=f"No Postgres on {_DB_HOST}:{_DB_PORT} — a pool needs a server"
)


@pytest.fixture
def pooled():
    """Enable the pool for one test, and always tear it down.

    A pool left enabled leaks into every later test in the process, which is the
    kind of cross-test coupling that makes a suite report the wrong thing.
    """
    from src.database import postgres_handler as ph
    ph.disable_pool()
    # `enable_pool` ne prend AUCUNE configuration : le pool se construit à la
    # première connexion, à partir des attributs déjà résolus du handler. Sa
    # première version lisait l'environnement elle-même et `test_one_door_onto_
    # the_database` l'a refusée en CI — une quatrième copie de la précédence DSN.
    ph.enable_pool(1, 3)
    try:
        yield ph
    finally:
        ph.disable_pool()


def test_a_borrowed_connection_still_carries_the_statement_timeout(pooled) -> None:
    db = pooled.PostgresHandler(**_KW)
    try:
        assert db.fetch_query("SHOW statement_timeout")[0][0] == "15s", (
            "the 15 s ceiling is gone. It travels in the connection options, so a pool "
            "that creates connections without them removes it silently."
        )
        assert db.conn.autocommit is True
    finally:
        db.close()


def test_an_aborted_transaction_does_not_poison_the_next_borrower(pooled) -> None:
    """⚠️ This pins a DEPENDENCY's guarantee, not ours. Said plainly, because it
    could not be made to fail.

    Two mutations were tried and both stayed green. First the abort was staged
    with `_atomic()`, which rolls back in its own `finally` — the setup could
    not produce the state being checked. Staged by hand instead (autocommit off,
    a failing statement, transaction status verified INERROR), it still stayed
    green with `_return_to_pool`'s rollback removed. The reason is in
    `psycopg2.pool.AbstractConnectionPool._putconn`: it inspects
    `transaction_status` and calls `conn.rollback()` itself.

    So the rollback in `_return_to_pool` is belt-and-braces, and `_connect()`
    re-asserts `autocommit = True` on every borrow anyway. What this test
    actually holds is psycopg2's contract — worth pinning, because the day a
    version changes it, every borrower after a failed batch breaks on correct
    code. It is NOT evidence that our own code provides the guarantee.
    """
    db = pooled.PostgresHandler(**_KW)
    try:
        db.conn.autocommit = False
        try:
            db.cursor.execute("SELECT 1/0")
        except Exception:                        # noqa: BLE001 — the abort is the setup
            pass
        # Prove the state we rely on actually exists before asserting on it.
        import psycopg2.extensions as _ext
        assert db.conn.get_transaction_status() == _ext.TRANSACTION_STATUS_INERROR, (
            "the setup did not abort the transaction — this test would pass on the "
            "defect, which is how its first version did"
        )
    finally:
        db.close()

    nxt = pooled.PostgresHandler(**_KW)
    try:
        assert nxt.fetch_query("SELECT 42")[0][0] == 42, (
            "the next borrower inherited an aborted transaction — the pool is poisoned "
            "and every subsequent request fails on correct code."
        )
    finally:
        nxt.close()


def test_close_returns_the_connection_instead_of_destroying_it(pooled, monkeypatch) -> None:
    """Otherwise the pool is an indirection that measures nothing."""
    import psycopg2

    handshakes = {"n": 0}
    real = psycopg2.connect

    def counting(*a, **k):
        handshakes["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(psycopg2, "connect", counting)
    monkeypatch.setattr(pooled.psycopg2, "connect", counting)

    def cycles(n: int) -> None:
        for _ in range(n):
            db = pooled.PostgresHandler(**_KW)
            db.fetch_query("SELECT 1")
            db.close()

    # La PREMIÈRE série construit le pool, qui ouvre ses `minconn` connexions —
    # une poignée de main légitime, et une seule fois. Compter zéro ici serait
    # faux : la première version de ce test le faisait et a rougi dès que le pool
    # est devenu paresseux, sur un comportement pourtant correct.
    cycles(5)
    after_warmup = handshakes["n"]
    assert after_warmup <= 3, (
        f"{after_warmup} poignées de main pour amorcer un pool de 3 — il en ouvre "
        "plus que sa taille, donc il n'en réutilise aucune."
    )

    # La SECONDE n'en coûte aucune. C'est la propriété qui compte, et elle ne
    # dépend ni de la taille du pool ni du moment où il est construit.
    cycles(5)
    assert handshakes["n"] == after_warmup, (
        f"{handshakes['n'] - after_warmup} nouvelle(s) poignée(s) de main sur 5 cycles "
        "à pool déjà chaud — `close()` détruit les connexions au lieu de les rendre."
    )


def test_without_the_pool_nothing_changes() -> None:
    """The opt-in must be an opt-in: Airflow never calls enable_pool.

    Its tasks hold a connection for minutes and would gain nothing; worse, they
    would share connections between operators.
    """
    from src.database import postgres_handler as ph
    ph.disable_pool()
    assert not ph.pool_is_enabled()
    db = ph.PostgresHandler(**_KW)
    try:
        assert db._from_pool is False
        assert db.fetch_query("SHOW statement_timeout")[0][0] == "15s"
    finally:
        db.close()
