"""The brute-force lockout: an attempt is CLAIMED before bcrypt, by the database (R370 a, R398 a).

Type: Utility
Uses: PostgresHandler (fetch_query)
Triggers: src/dashboard/auth.py (password and TOTP), src/api/auth.py — every login attempt
Persists in: saas_users.failed_login_attempts, saas_users.locked_until

R370 moved the increment into one statement: eight concurrent wrong passwords used to
count as one. It still ran AFTER bcrypt, behind a `locked_until` read taken with the
user row — a parallel burst all read « not locked » and all reached bcrypt, 4 + N tries
per window. R398: the attempt is counted BEFORE bcrypt, and only if the account is not
locked, in one UPDATE that Postgres serialises per row. Whatever the concurrency, at
most MAX_LOGIN_ATTEMPTS checks run per window; a right answer resets the counter.

An expired lock opens a FRESH window (the count restarts at 1). Without it, the first
claim after expiry found the old count ≥ 5 and relocked the account — before the
password was even checked, so the owner typing the right one was locked out again.

Guards: tests/test_the_login_lockout_counts_every_failure.py,
tests/test_second_factor_is_not_brute_forceable.py.
"""
from __future__ import annotations

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# The count this claim produces — read twice in the UPDATE below. In a SET clause every
# column reference is the row's value BEFORE the update, so both reads agree.
_NEXT_COUNT = ("(CASE WHEN locked_until IS NOT NULL AND locked_until <= NOW() THEN 1 "
               "ELSE failed_login_attempts + 1 END)")

_CLAIM_SQL = (
    "UPDATE saas_users SET failed_login_attempts = " + _NEXT_COUNT + ", "
    "locked_until = CASE WHEN " + _NEXT_COUNT + " >= %s "
    "                    THEN NOW() + make_interval(mins => %s) "
    "                    WHEN locked_until <= NOW() THEN NULL "
    "                    ELSE locked_until END "
    "WHERE id = %s AND (locked_until IS NULL OR locked_until <= NOW()) "
    "RETURNING id"
)


def claim_login_attempt(db, user_id: int) -> bool:
    """Count one attempt before checking it. False = the account is locked: check nothing."""
    return bool(db.fetch_query(_CLAIM_SQL, (MAX_LOGIN_ATTEMPTS, LOCKOUT_MINUTES, user_id)))


def minutes_left(db, user_id: int) -> int:
    """Whole minutes until the lock lifts (at least 1) — for the « réessayez dans » message."""
    rows = db.fetch_query(
        "SELECT CEIL(EXTRACT(EPOCH FROM (locked_until - NOW())) / 60) "
        "FROM saas_users WHERE id = %s AND locked_until > NOW()", (user_id,))
    return max(int(rows[0][0] or 1), 1) if rows else 1
