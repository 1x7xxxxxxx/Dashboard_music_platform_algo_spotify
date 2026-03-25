"""Per-platform circuit breaker stored in etl_circuit_breaker table.

Prevents wasting Airflow retries when credentials are known-broken or
an API is down. State machine: CLOSED → OPEN → HALF_OPEN → CLOSED.

States:
  CLOSED     Normal operation. Failure count incremented on each error.
  OPEN       Too many failures. Callers should skip collection.
             Automatically transitions to HALF_OPEN after reset_after_hours.
  HALF_OPEN  One test request allowed. Success → CLOSED. Failure → OPEN.

Usage in a DAG task:

    from src.utils.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(platform='soundcloud', artist_id=1)
    if cb.is_open():
        logger.warning(cb.open_reason())
        return  # skip gracefully

    try:
        rows = collector.run()
        cb.record_success()
    except Exception as e:
        cb.record_failure(str(e))
        raise
"""
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CLOSED    = 'closed'
OPEN      = 'open'
HALF_OPEN = 'half_open'

_FAILURE_THRESHOLD  = 3    # failures before opening
_RESET_AFTER_HOURS  = 6    # hours before half_open attempt


def _conn():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'postgres'),
        port=int(os.getenv('DATABASE_PORT', 5432)),
        database=os.getenv('DATABASE_NAME', 'spotify_etl'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD', ''),
    )


class CircuitBreaker:
    def __init__(
        self,
        platform: str,
        artist_id: int = 0,
        failure_threshold: int = _FAILURE_THRESHOLD,
        reset_after_hours: int = _RESET_AFTER_HOURS,
    ):
        self.platform = platform
        self.artist_id = artist_id
        self.failure_threshold = failure_threshold
        self.reset_after_hours = reset_after_hours
        self._row = self._load()

    # ── Public API ────────────────────────────────────────────────

    def is_open(self) -> bool:
        """Return True if the circuit is OPEN (caller should skip collection)."""
        self._row = self._load()  # refresh state
        state = self._row.get('state', CLOSED)
        if state == CLOSED:
            return False
        if state == HALF_OPEN:
            return False  # allow one test
        # OPEN — check if reset window has passed
        reset_at = self._row.get('reset_at')
        if reset_at and datetime.utcnow() >= reset_at:
            self._transition(HALF_OPEN)
            return False
        return True

    def record_success(self):
        """Call after a successful collection run."""
        prev_state = self._row.get('state', CLOSED)
        if prev_state != CLOSED:
            logger.info(
                f"CircuitBreaker [{self.platform}/{self.artist_id}]: "
                f"{prev_state} → CLOSED after successful run."
            )
        self._upsert(state=CLOSED, failure_count=0, last_error=None,
                     last_failure_at=None, opened_at=None, reset_at=None)

    def record_failure(self, error: str = ''):
        """Call after a failed collection run."""
        row = self._load()
        failure_count = row.get('failure_count', 0) + 1
        now = datetime.utcnow()

        if failure_count >= self.failure_threshold:
            reset_at = now + timedelta(hours=self.reset_after_hours)
            self._upsert(
                state=OPEN,
                failure_count=failure_count,
                last_error=error[:500],
                last_failure_at=now,
                opened_at=row.get('opened_at') or now,
                reset_at=reset_at,
            )
            logger.warning(
                f"CircuitBreaker [{self.platform}/{self.artist_id}]: "
                f"OPEN after {failure_count} failures. "
                f"Will retry at {reset_at.strftime('%Y-%m-%d %H:%M')} UTC. "
                f"Last error: {error[:100]}"
            )
        else:
            self._upsert(
                state=CLOSED,
                failure_count=failure_count,
                last_error=error[:500],
                last_failure_at=now,
                opened_at=None,
                reset_at=None,
            )
            logger.info(
                f"CircuitBreaker [{self.platform}/{self.artist_id}]: "
                f"failure {failure_count}/{self.failure_threshold}. Still CLOSED."
            )

    def open_reason(self) -> str:
        """Human-readable explanation when circuit is open."""
        row = self._row
        failure_count = row.get('failure_count', 0)
        opened_at = row.get('opened_at')
        reset_at = row.get('reset_at')
        last_error = row.get('last_error', '')
        opened_str = opened_at.strftime('%Y-%m-%d %H:%M UTC') if opened_at else 'unknown'
        reset_str  = reset_at.strftime('%Y-%m-%d %H:%M UTC')  if reset_at  else 'unknown'
        return (
            f"Circuit OPEN for {self.platform} (artist {self.artist_id}): "
            f"{failure_count} failures since {opened_str}. "
            f"Next retry: {reset_str}. Last error: {last_error[:100]}"
        )

    def reset(self):
        """Manually force circuit back to CLOSED (admin action)."""
        self._upsert(state=CLOSED, failure_count=0, last_error=None,
                     last_failure_at=None, opened_at=None, reset_at=None)
        logger.info(f"CircuitBreaker [{self.platform}/{self.artist_id}]: manually RESET to CLOSED.")

    # ── Internal ──────────────────────────────────────────────────

    def _load(self) -> dict:
        try:
            c = _conn()
            cur = c.cursor()
            cur.execute(
                "SELECT state, failure_count, last_failure_at, opened_at, reset_at, last_error "
                "FROM etl_circuit_breaker WHERE platform = %s AND artist_id = %s",
                (self.platform, self.artist_id),
            )
            row = cur.fetchone()
            cur.close()
            c.close()
            if not row:
                return {}
            keys = ['state', 'failure_count', 'last_failure_at', 'opened_at', 'reset_at', 'last_error']
            return dict(zip(keys, row))
        except Exception as e:
            logger.debug(f"CircuitBreaker: DB load failed — {e}")
            return {}

    def _transition(self, new_state: str):
        row = self._load()
        self._upsert(
            state=new_state,
            failure_count=row.get('failure_count', 0),
            last_error=row.get('last_error'),
            last_failure_at=row.get('last_failure_at'),
            opened_at=row.get('opened_at'),
            reset_at=row.get('reset_at'),
        )

    def _upsert(self, state, failure_count, last_error,
                last_failure_at, opened_at, reset_at):
        try:
            c = _conn()
            cur = c.cursor()
            cur.execute(
                """
                INSERT INTO etl_circuit_breaker
                    (platform, artist_id, state, failure_count,
                     last_failure_at, opened_at, reset_at, last_error, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (platform, artist_id) DO UPDATE SET
                    state           = EXCLUDED.state,
                    failure_count   = EXCLUDED.failure_count,
                    last_failure_at = EXCLUDED.last_failure_at,
                    opened_at       = EXCLUDED.opened_at,
                    reset_at        = EXCLUDED.reset_at,
                    last_error      = EXCLUDED.last_error,
                    updated_at      = NOW()
                """,
                (self.platform, self.artist_id, state, failure_count,
                 last_failure_at, opened_at, reset_at, last_error),
            )
            c.commit()
            cur.close()
            c.close()
        except Exception as e:
            logger.debug(f"CircuitBreaker: DB write failed — {e}")


# ── Admin helpers ─────────────────────────────────────────────────

def get_all_circuit_states() -> list[dict]:
    """Return all circuit breaker rows for dashboard display."""
    try:
        c = _conn()
        cur = c.cursor()
        cur.execute(
            """
            SELECT platform, artist_id, state, failure_count,
                   last_failure_at, reset_at, last_error, updated_at
            FROM etl_circuit_breaker
            ORDER BY state DESC, updated_at DESC
            """
        )
        rows = cur.fetchall()
        cur.close()
        c.close()
        keys = ['platform', 'artist_id', 'state', 'failure_count',
                'last_failure_at', 'reset_at', 'last_error', 'updated_at']
        return [dict(zip(keys, r)) for r in rows]
    except Exception as e:
        logger.warning(f"get_all_circuit_states: {e}")
        return []


def reset_circuit(platform: str, artist_id: int = 0):
    """Force-reset a specific circuit to CLOSED (for dashboard admin use)."""
    CircuitBreaker(platform=platform, artist_id=artist_id).reset()
