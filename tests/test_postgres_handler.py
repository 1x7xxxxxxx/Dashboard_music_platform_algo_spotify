"""Unit tests — PostgresHandler (mocked psycopg2).

Ce que ces tests ont VRAIMENT fait pendant un temps (mesuré le 2026-09-16)
-------------------------------------------------------------------------
`_make_handler()` patche `src.database.postgres_handler.psycopg2.connect` et croit
donc rendre un handler entièrement simulé. **Ce n'est vrai que si le pool de
connexions du processus est désarmé.**

`_connect()` demande d'abord `_borrow_from_pool()`. Quand le pool existe — et il
existe dès qu'un test ANTÉRIEUR du même worker a appelé `get_db_connection()`, ce
que font des dizaines de fichiers — la connexion vient du `ThreadedConnectionPool`,
dont les sockets ont été ouverts AVANT que le patch existe. Le patch est donc
contourné, et le handler tient un **vrai curseur Postgres**.

Mesuré, sur le même interpréteur :

    pool désarmé  -> type(handler.cursor) == MagicMock
    pool armé     -> type(handler.cursor) == cursor        (le vrai)

Ce fichier devenait alors un test d'INTÉGRATION qui se présente comme unitaire, et
c'est la partie coûteuse : un vrai curseur répond à `execute` et à `fetchall`, donc
23 de ses 24 tests passaient quand même — en affirmant sur la base ce qu'ils
croyaient affirmer sur un mock. Un seul a rougi, `test_returns_rows`, parce qu'il
pose un `.return_value` sur une méthode réelle :
`AttributeError: 'builtin_function_or_method' object has no attribute 'return_value'`.

Deux remèdes, et il en faut deux
--------------------------------
* la fixture ci-dessous rend ce fichier INDÉPENDANT de ses voisins : le pool est mis
  de côté le temps de chaque test, puis remis. On ne le FERME pas (`disable_pool()`
  couperait les connexions que d'autres tests tiennent) — on l'écarte ;
* `_make_handler()` VÉRIFIE que le mock a pris. Sans cette assertion, la prochaine
  façon de contourner le patch redeviendrait silencieuse, et le silence est le
  défaut. Un test qui ment sur ce qu'il mesure est pire qu'un test absent.
"""
import contextlib
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.database.postgres_handler import PostgresHandler


@contextlib.contextmanager
def _pool_set_aside():
    """Le pool du processus est écarté le temps du bloc, puis remis — jamais fermé."""
    from src.database import postgres_handler as _ph
    saved, saved_limits = _ph._POOL, _ph._POOL_LIMITS
    _ph._POOL, _ph._POOL_LIMITS = None, None
    try:
        yield
    finally:
        _ph._POOL, _ph._POOL_LIMITS = saved, saved_limits


@pytest.fixture(autouse=True)
def _no_pool_behind_the_mock():
    """Le pool du processus est écarté : un mock ne doit pas tomber sur une vraie base."""
    with _pool_set_aside():
        yield


# =============================================================================
# Helpers
# =============================================================================

def _make_handler():
    """Return a PostgresHandler with a mocked psycopg2 connection."""
    with patch("src.database.postgres_handler.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.cursor.return_value = MagicMock()
        mock_connect.return_value = mock_conn
        handler = PostgresHandler(
            host="localhost", port=5433, database="test_db",
            user="user", password="pass"  # pragma: allowlist secret
        )
    assert isinstance(handler.cursor, MagicMock), (
        f"le patch de psycopg2.connect a été CONTOURNÉ : `handler.cursor` est un "
        f"{type(handler.cursor).__name__}, donc ce « test unitaire » parle à une VRAIE "
        "base. Cause connue : le pool de connexions du processus était armé, et "
        "`_connect()` emprunte au pool avant de regarder `psycopg2.connect`. "
        "La fixture `_no_pool_behind_the_mock` existe pour ça — a-t-elle été retirée ?"
    )
    return handler


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity, class `a-unit-test-that-borrows-a-real-connection-from-the-pool`,
    without depending on which neighbour ran first: a pool ARMED behind the patch —
    the 2026-09-16 state — makes `_make_handler` refuse its handler; the same pool set
    aside by `_pool_set_aside` lets the mock through."""
    from src.database import postgres_handler as _ph

    class _ArmedPool:
        def getconn(self):
            conn = type("RealLooking", (), {})()
            conn.closed = False
            conn.cursor = lambda *a, **k: object()
            conn.autocommit = True
            return conn

        def putconn(self, *a, **k):
            pass

    _ph._POOL = _ArmedPool()
    try:
        with pytest.raises(AssertionError, match="CONTOURNÉ"):
            _make_handler()
        with _pool_set_aside():
            assert isinstance(_make_handler().cursor, MagicMock)
    finally:
        _ph._POOL = None


# =============================================================================
# from_url
# =============================================================================

class TestFromURL:
    def test_encoded_credentials_are_decoded_like_libpq(self):
        """`p%40ss%3Aw` is how `p@ss:w` must be written in a URL — and libpq decodes it.
        Passed through still encoded, authentication failed (found 2026-09-24)."""
        with patch("src.database.postgres_handler.psycopg2.connect"):
            h = PostgresHandler.from_url("postgresql://us%2Fer:p%40ss%3Aw@host:5432/db")
        assert (h.user, h.password) == ("us/er", "p@ss:w")
        with patch("src.database.postgres_handler.psycopg2.connect"):
            plain = PostgresHandler.from_url("postgresql://user:plain@host:5432/db")
        assert plain.password == "plain", "a password with no escape must pass unchanged"  # pragma: allowlist secret — fabricated

    def test_postgres_scheme(self):
        with patch("src.database.postgres_handler.psycopg2.connect"):
            h = PostgresHandler.from_url("postgres://user:pass@localhost:5433/mydb")
        assert h.host == "localhost"
        assert h.port == 5433
        assert h.database == "mydb"
        assert h.user == "user"

    def test_postgresql_scheme(self):
        with patch("src.database.postgres_handler.psycopg2.connect"):
            h = PostgresHandler.from_url("postgresql://u:p@host:5432/db")
        assert h.database == "db"

    def test_invalid_scheme_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            PostgresHandler.from_url("mysql://user:pass@host/db")

    def test_default_port_when_missing(self):
        with patch("src.database.postgres_handler.psycopg2.connect"):
            h = PostgresHandler.from_url("postgres://user:pass@host/db")
        assert h.port == 5432


# =============================================================================
# _connect
# =============================================================================

class TestConnect:
    def test_connect_sets_autocommit(self):
        with patch("src.database.postgres_handler.psycopg2.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.closed = False
            mock_connect.return_value = mock_conn
            PostgresHandler(host="h", port=5432, database="db", user="u", password="p")  # pragma: allowlist secret
        assert mock_conn.autocommit is True

    def test_connect_failure_raises(self):
        import psycopg2
        with patch("src.database.postgres_handler.psycopg2.connect",
                   side_effect=psycopg2.OperationalError("refused")):
            with pytest.raises(psycopg2.OperationalError):
                PostgresHandler(host="h", port=5432, database="db", user="u", password="p")  # pragma: allowlist secret


# =============================================================================
# _ensure_connection
# =============================================================================

class TestEnsureConnection:
    def test_reconnects_when_conn_closed(self):
        handler = _make_handler()
        handler.conn.closed = True

        with patch.object(handler, "_connect") as mock_reconnect:
            handler._ensure_connection()
            mock_reconnect.assert_called_once()

    def test_reconnects_on_operational_error(self):
        import psycopg2
        handler = _make_handler()
        handler.conn.closed = False
        handler.conn.poll.side_effect = psycopg2.OperationalError("lost")

        with patch.object(handler, "_connect") as mock_reconnect:
            handler._ensure_connection()
            mock_reconnect.assert_called_once()

    def test_no_reconnect_when_healthy(self):
        handler = _make_handler()
        handler.conn.closed = False
        handler.conn.poll.return_value = None  # no exception

        with patch.object(handler, "_connect") as mock_reconnect:
            handler._ensure_connection()
            mock_reconnect.assert_not_called()


# =============================================================================
# fetch_query
# =============================================================================

class TestFetchQuery:
    def test_returns_rows(self):
        handler = _make_handler()
        handler.cursor.fetchall.return_value = [("row1",), ("row2",)]
        result = handler.fetch_query("SELECT 1")
        assert result == [("row1",), ("row2",)]

    def test_raises_on_cursor_error(self):
        import psycopg2
        handler = _make_handler()
        handler.cursor.execute.side_effect = psycopg2.ProgrammingError("bad sql")
        with pytest.raises(psycopg2.ProgrammingError):
            handler.fetch_query("SELECT bad syntax")


# =============================================================================
# fetch_df
# =============================================================================

class TestFetchDF:
    def test_returns_dataframe_with_correct_columns(self):
        import pandas as pd
        handler = _make_handler()
        handler.cursor.description = [("col_a",), ("col_b",)]
        handler.cursor.fetchall.return_value = [(1, "x"), (2, "y")]

        df = handler.fetch_df("SELECT col_a, col_b FROM t")
        assert list(df.columns) == ["col_a", "col_b"]
        assert len(df) == 2
        assert df.iloc[0]["col_a"] == 1

    def test_empty_result_returns_empty_dataframe(self):
        handler = _make_handler()
        handler.cursor.description = [("id",)]
        handler.cursor.fetchall.return_value = []

        df = handler.fetch_df("SELECT id FROM t WHERE false")
        assert len(df) == 0
        assert "id" in df.columns


# =============================================================================
# insert_many
# =============================================================================

class TestInsertMany:
    def test_empty_data_returns_zero(self):
        handler = _make_handler()
        result = handler.insert_many("some_table", [])
        assert result == 0
        handler.cursor.executemany.assert_not_called()

    def test_inserts_correct_number_of_rows(self):
        # Use an allowlisted table name. postgres_handler.validate_table
        # rejects anything not in _ALLOWED_TABLES (SQL-injection guard added
        # in commit d65b0a6). Table identity is irrelevant for this test —
        # only that validation passes so insert_many's row-counting logic
        # is exercised.
        handler = _make_handler()
        data = [{"col_a": 1, "col_b": "x"}, {"col_a": 2, "col_b": "y"}]
        # `execute_batch`, plus `executemany` : depuis le 2026-09-10, `insert_many`
        # envoie son lot dans UNE transaction. `executemany` sous `autocommit = True`
        # en ouvrait une par ligne, donc un échec au milieu laissait la première
        # moitié committée. Ce test suit la même forme que `TestUpsertMany`, qui
        # patchait déjà `execute_batch` — c'est la migration qui n'était pas venue
        # jusqu'ici.
        with patch("src.database.postgres_handler.execute_batch") as mock_batch:
            result = handler.insert_many("subscription_plans", data)
        assert result == 2
        mock_batch.assert_called_once()
        handler.cursor.executemany.assert_not_called()


# =============================================================================
# upsert_many
# =============================================================================

class TestUpsertMany:
    def test_empty_data_returns_zero(self):
        handler = _make_handler()
        result = handler.upsert_many("t", [], ["id"], ["col_a"])
        assert result == 0

    def test_deduplicates_by_conflict_columns(self):
        from psycopg2.extras import execute_batch
        handler = _make_handler()
        handler.cursor.rowcount = 1

        data = [
            {"artist_id": 1, "isrc": "FR123", "value": 10},
            {"artist_id": 1, "isrc": "FR123", "value": 20},  # duplicate key
        ]
        with patch("src.database.postgres_handler.execute_batch") as mock_batch:
            # "subscription_plans" is an allowlisted placeholder (cf. comment
            # on test_inserts_correct_number_of_rows). Table identity is
            # irrelevant — dedup logic is what's tested.
            handler.upsert_many("subscription_plans", data, ["artist_id", "isrc"], ["value"])
            args = mock_batch.call_args[0]
            # Third argument is the values list — should be deduplicated to 1 row
            assert len(args[2]) == 1

    def test_no_dedup_for_functional_index_conflict(self):
        """Conflict columns with '(' prefix (SQL expressions) must not be used for dedup."""
        handler = _make_handler()
        handler.cursor.rowcount = 2
        data = [{"col": 1}, {"col": 2}]
        with patch("src.database.postgres_handler.execute_batch") as mock_batch:
            handler.upsert_many("subscription_plans", data, ["(col::date)"], ["col"])
            args = mock_batch.call_args[0]
            assert len(args[2]) == 2  # no dedup applied

    def test_raises_on_db_error(self):
        import psycopg2
        handler = _make_handler()
        with patch("src.database.postgres_handler.execute_batch",
                   side_effect=psycopg2.IntegrityError("constraint")):
            with pytest.raises(psycopg2.IntegrityError):
                handler.upsert_many("subscription_plans", [{"id": 1}], ["id"], ["id"])


# =============================================================================
# table_exists
# =============================================================================

class TestTableExists:
    def test_returns_true_when_table_exists(self):
        handler = _make_handler()
        handler.cursor.fetchall.return_value = [(True,)]
        assert handler.table_exists("my_table") is True

    def test_returns_false_when_table_missing(self):
        handler = _make_handler()
        handler.cursor.fetchall.return_value = [(False,)]
        assert handler.table_exists("missing_table") is False


# =============================================================================
# Context manager
# =============================================================================

class TestContextManager:
    def test_close_called_on_exit(self):
        handler = _make_handler()
        with patch.object(handler, "close") as mock_close:
            with handler:
                pass
            mock_close.assert_called_once()

    def test_close_called_on_exception(self):
        handler = _make_handler()
        with patch.object(handler, "close") as mock_close:
            with pytest.raises(ValueError):
                with handler:
                    raise ValueError("boom")
            mock_close.assert_called_once()
