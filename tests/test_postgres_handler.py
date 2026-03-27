"""Unit tests — PostgresHandler (mocked psycopg2)."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.database.postgres_handler import PostgresHandler


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
            user="user", password="pass"
        )
    return handler


# =============================================================================
# from_url
# =============================================================================

class TestFromURL:
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
            PostgresHandler(host="h", port=5432, database="db", user="u", password="p")
        assert mock_conn.autocommit is True

    def test_connect_failure_raises(self):
        import psycopg2
        with patch("src.database.postgres_handler.psycopg2.connect",
                   side_effect=psycopg2.OperationalError("refused")):
            with pytest.raises(psycopg2.OperationalError):
                PostgresHandler(host="h", port=5432, database="db", user="u", password="p")


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
        handler = _make_handler()
        data = [{"col_a": 1, "col_b": "x"}, {"col_a": 2, "col_b": "y"}]
        result = handler.insert_many("my_table", data)
        assert result == 2
        handler.cursor.executemany.assert_called_once()


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
            handler.upsert_many("t", data, ["artist_id", "isrc"], ["value"])
            args = mock_batch.call_args[0]
            # Third argument is the values list — should be deduplicated to 1 row
            assert len(args[2]) == 1

    def test_no_dedup_for_functional_index_conflict(self):
        """Conflict columns with '(' prefix (SQL expressions) must not be used for dedup."""
        handler = _make_handler()
        handler.cursor.rowcount = 2
        data = [{"col": 1}, {"col": 2}]
        with patch("src.database.postgres_handler.execute_batch") as mock_batch:
            handler.upsert_many("t", data, ["(col::date)"], ["col"])
            args = mock_batch.call_args[0]
            assert len(args[2]) == 2  # no dedup applied

    def test_raises_on_db_error(self):
        import psycopg2
        handler = _make_handler()
        with patch("src.database.postgres_handler.execute_batch",
                   side_effect=psycopg2.IntegrityError("constraint")):
            with pytest.raises(psycopg2.IntegrityError):
                handler.upsert_many("t", [{"id": 1}], ["id"], ["id"])


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
