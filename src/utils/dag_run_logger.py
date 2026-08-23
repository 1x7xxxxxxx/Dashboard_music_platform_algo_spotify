"""ETL run logger — persists DAG run metrics to etl_run_log table.

Usage (context manager inside any DAG task):

    with DagRunLogger('soundcloud_daily', artist_id=1, platform='soundcloud') as run:
        rows = collector.run()
        run.rows_inserted = rows

The context manager writes a 'running' row on enter, then updates it
to 'success' or 'failed' on exit. Exceptions are re-raised after logging.
"""
import logging
import json
from datetime import datetime, timezone

from src.utils.safe_error import safe_error

logger = logging.getLogger(__name__)

_STATUS_RUNNING  = 'running'
_STATUS_SUCCESS  = 'success'
_STATUS_FAILED   = 'failed'
_STATUS_SKIPPED  = 'skipped'
_STATUS_PARTIAL  = 'partial'


def _get_db():
    # See src.utils.pg_connect: this was one of four hand-rolled DSNs that did
    # not agree on the host default.
    from src.utils.pg_connect import connect

    return connect()


class DagRunLogger:
    """Context manager that writes start/end metrics to etl_run_log."""

    def __init__(
        self,
        dag_id: str,
        artist_id: int = None,
        platform: str = None,
        run_id: str = None,
        extra_context: dict = None,
    ):
        self.dag_id = dag_id
        self.artist_id = artist_id
        self.platform = platform
        self.run_id = run_id
        self.extra_context = extra_context or {}
        self.rows_inserted = 0
        self.rows_failed = 0
        self._log_id = None
        self._started_at = None
        self._skipped_reason = None

    def skip(self, reason: str) -> None:
        """Record that this tenant was deliberately not collected, and why.

        `skipped` is NOT a failure and must not read as one: a tenant who has not
        declared an identity for this platform is in a correct state. But it must not
        be ABSENT from the ledger either — absence is what made `etl_run_log` unable
        to answer "did collection run for this tenant?", the question that left
        Benken's YouTube silent for two nights. A skipped row says "we looked, and
        here is why there is nothing", which is a different sentence from no row.
        """
        self._skipped_reason = reason

    def __enter__(self):
        self._started_at = datetime.now(timezone.utc)
        try:
            conn = _get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO etl_run_log
                    (dag_id, artist_id, platform, run_id, started_at, status, extra_context)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    self.dag_id,
                    self.artist_id,
                    self.platform,
                    self.run_id,
                    self._started_at,
                    _STATUS_RUNNING,
                    json.dumps(self.extra_context),
                ),
            )
            self._log_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            logger.debug(f"etl_run_log: started run id={self._log_id} dag={self.dag_id}")
        except Exception as e:
            logger.warning(f"etl_run_log: could not write start record — {safe_error(e)}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ended_at = datetime.now(timezone.utc)
        duration_ms = int((ended_at - self._started_at).total_seconds() * 1000) if self._started_at else None

        if exc_type is None and self._skipped_reason is not None:
            status = _STATUS_SKIPPED
            error_type = None
            error_msg = self._skipped_reason[:1000]
        elif exc_type is None:
            status = _STATUS_SUCCESS if self.rows_failed == 0 else _STATUS_PARTIAL
            error_type = None
            error_msg = None
        else:
            status = _STATUS_FAILED
            error_type = exc_type.__name__ if exc_type else None
            # safe_error, NOT str(): this message is PERSISTED and then rendered by
            # src/dashboard/views/etl_logs.py and alerts.py. The exception arrives as an
            # __exit__ PARAMETER, not as an `except … as e`, so the AST guard in
            # tests/test_credentials_security.py could not see it — the one shape its
            # detector is blind to by construction. Class secret-in-an-exception-message.
            error_msg = safe_error(exc_val, limit=1000) if exc_val else None

        try:
            conn = _get_db()
            cur = conn.cursor()
            if self._log_id:
                cur.execute(
                    """
                    UPDATE etl_run_log SET
                        ended_at      = %s,
                        duration_ms   = %s,
                        rows_inserted = %s,
                        rows_failed   = %s,
                        status        = %s,
                        error_type    = %s,
                        error_message = %s
                    WHERE id = %s
                    """,
                    (
                        ended_at, duration_ms,
                        self.rows_inserted, self.rows_failed,
                        status, error_type, error_msg,
                        self._log_id,
                    ),
                )
            conn.commit()
            cur.close()
            conn.close()
            level = (logger.info if status in (_STATUS_SUCCESS, _STATUS_PARTIAL, _STATUS_SKIPPED)
                     else logger.error)
            level(
                f"etl_run_log: {self.dag_id} [{self.platform or '—'}] → {status} "
                f"({self.rows_inserted} rows, {duration_ms}ms)"
            )
        except Exception as e:
            logger.warning(f"etl_run_log: could not write end record — {safe_error(e)}")

        return False  # never suppress exceptions


def record_tenant_run(dag_id: str, artist_id: int, platform: str, run_id: str = None,
                      status: str = _STATUS_SUCCESS, rows: int = 0,
                      exc: BaseException = None, reason: str = None) -> None:
    """Write ONE finished etl_run_log row for one (tenant, platform) outcome.

    Why this exists alongside `DagRunLogger` — the collection DAGs already isolate
    failures per tenant: a `try` whose `except` logs, appends to a per-artist error
    list and `continue`s, so the fleet is never aborted by one tenant. A context
    manager cannot sit inside that shape without either re-indenting the whole loop
    body or swallowing the exception the loop is deliberately catching. One call at
    each exit point of the loop expresses the same fact with none of that.

    The three outcomes are deliberately distinct, and `skipped` is the one that was
    missing everywhere: a tenant who has not declared an identity is in a CORRECT
    state, but it must still leave a row. Absence of a row is what made this ledger
    unable to answer "did collection run for this tenant?" — the question with no
    other answer, and the reason Benken's YouTube could fail two nights in a row
    with every surface green.

    Never raises: bookkeeping must not be able to fail the collection it observes.
    """
    now = datetime.now(timezone.utc)
    # safe_error, NOT str(): this message is PERSISTED and rendered by
    # src/dashboard/views/etl_logs.py. An HTTP exception message embeds the prepared
    # URL, and several upstream APIs take their credential as a query parameter.
    error_msg = safe_error(exc, limit=1000) if exc is not None else (
        reason[:1000] if reason else None)
    try:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO etl_run_log
                (dag_id, artist_id, platform, run_id, started_at, ended_at,
                 rows_inserted, status, error_type, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (dag_id, artist_id, platform, run_id, now, now, rows, status,
             type(exc).__name__ if exc is not None else None, error_msg),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"etl_run_log: could not record {dag_id}/{artist_id} — {safe_error(e)}")


def record_tenant_success(dag_id, artist_id, platform, rows, run_id=None) -> None:
    record_tenant_run(dag_id, artist_id, platform, run_id,
                      status=_STATUS_SUCCESS, rows=rows or 0)


def record_tenant_failure(dag_id, artist_id, platform, exc, run_id=None) -> None:
    record_tenant_run(dag_id, artist_id, platform, run_id,
                      status=_STATUS_FAILED, exc=exc)


def record_tenant_skip(dag_id, artist_id, platform, reason, run_id=None) -> None:
    record_tenant_run(dag_id, artist_id, platform, run_id,
                      status=_STATUS_SKIPPED, reason=reason)
