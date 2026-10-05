"""The brute-force lockout counter, incremented by the database (R370 a).

Type: Utility
Uses: PostgresHandler (execute_query)
Triggers: src/dashboard/auth.py, src/api/auth.py — every wrong password
Persists in: saas_users.failed_login_attempts, saas_users.locked_until

Both login paths used to read the counter with the user row and write `count + 1`
back after bcrypt: eight concurrent wrong passwords counted as one, so the threshold
never tripped. One statement increments and locks; Postgres serialises it per row.
Guard: tests/test_the_login_lockout_counts_every_failure.py.
"""
from __future__ import annotations

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def record_password_failure(db, user_id: int) -> None:
    """Count one wrong password and lock the account once the threshold is reached."""
    db.execute_query(
        "UPDATE saas_users SET failed_login_attempts = failed_login_attempts + 1, "
        "locked_until = CASE WHEN failed_login_attempts + 1 >= %s "
        "                    THEN NOW() + make_interval(mins => %s) ELSE locked_until END "
        "WHERE id = %s",
        (MAX_LOGIN_ATTEMPTS, LOCKOUT_MINUTES, user_id),
    )
