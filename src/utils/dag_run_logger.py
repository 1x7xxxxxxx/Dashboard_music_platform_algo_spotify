"""ETL run logger — persists DAG run metrics to etl_run_log table.

Usage (context manager inside any DAG task):

    with DagRunLogger('soundcloud_daily', artist_id=1, platform='soundcloud') as run:
        rows = collector.run()
        run.rows_inserted = rows

The context manager writes a 'running' row on enter, then updates it
to 'success' or 'failed' on exit. Exceptions are re-raised after logging.
"""
import logging
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)

_STATUS_RUNNING  = 'running'
_STATUS_SUCCESS  = 'success'
_STATUS_FAILED   = 'failed'
_STATUS_SKIPPED  = 'skipped'
_STATUS_PARTIAL  = 'partial'


def _get_db():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD', ''),
    )


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

    def __enter__(self):
        self._started_at = datetime.utcnow()
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
            logger.warning(f"etl_run_log: could not write start record — {e}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ended_at = datetime.utcnow()
        duration_ms = int((ended_at - self._started_at).total_seconds() * 1000) if self._started_at else None

        if exc_type is None:
            status = _STATUS_SUCCESS if self.rows_failed == 0 else _STATUS_PARTIAL
            error_type = None
            error_msg = None
        else:
            status = _STATUS_FAILED
            error_type = exc_type.__name__ if exc_type else None
            error_msg = str(exc_val)[:1000] if exc_val else None

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
            level = logger.info if status in (_STATUS_SUCCESS, _STATUS_PARTIAL) else logger.error
            level(
                f"etl_run_log: {self.dag_id} [{self.platform or '—'}] → {status} "
                f"({self.rows_inserted} rows, {duration_ms}ms)"
            )
        except Exception as e:
            logger.warning(f"etl_run_log: could not write end record — {e}")

        return False  # never suppress exceptions
