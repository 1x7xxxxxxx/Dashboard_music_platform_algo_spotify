"""JWT token utilities for the FastAPI REST backend.

Secret key is read from the API_SECRET_KEY environment variable. If it is missing or
too short, an EPHEMERAL random secret is generated per process — dev/tests keep
working, but issued tokens do not survive a restart and are not shared across workers.
PRODUCTION MUST set API_SECRET_KEY (>=32 random chars, e.g. `openssl rand -hex 32`):
a multi-worker deploy with per-process ephemeral secrets would reject each other's
tokens. (The previous hardcoded fallback was a public string committed in the repo —
anyone could forge a valid JWT for any artist.)
"""
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

_env_secret = os.getenv("API_SECRET_KEY", "")
if len(_env_secret) >= 32:
    SECRET_KEY: str = _env_secret
else:
    SECRET_KEY = secrets.token_hex(32)  # ephemeral — never a repo-known constant
    logging.getLogger(__name__).warning(
        "API_SECRET_KEY %s — using an ephemeral random secret for this process. "
        "Set a >=32-char value in production (tokens won't survive restart / "
        "multi-worker otherwise).",
        "is set but <32 chars" if _env_secret else "is not set",
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 h

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Encode a JWT with an expiry claim."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT.  Raises ``JWTError`` on failure."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# Shared with the dashboard login (src/dashboard/auth.py) — same DB columns, so an
# API brute-force counts toward the SAME lockout as the dashboard.
_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def authenticate_api_user(db, username: str, password: str):
    """DB-backed login for the REST API against ``saas_users`` (the same accounts +
    bcrypt hashes as the dashboard). Self-contained: no config.yaml, no Streamlit
    import — works in the API container. Enforces the shared brute-force lockout and
    refuses 2FA-enabled accounts (a password-only token would bypass their 2FA).

    Returns ``(user_dict, None)`` on success, else ``(None, reason)`` with reason in
    {``invalid_credentials``, ``locked``, ``unverified``, ``totp_required``}.
    """
    from datetime import datetime, timezone

    ident = (username or "").strip()
    rows = db.fetch_query(
        "SELECT id, username, email, password_hash, artist_id, role, email_verified, "
        "       failed_login_attempts, locked_until, totp_enabled "
        "FROM saas_users WHERE (username = %s OR LOWER(email) = LOWER(%s)) "
        "AND active = TRUE LIMIT 1",
        (ident, ident),
    )
    if not rows:
        return None, "invalid_credentials"
    (uid, uname, email, pw_hash, artist_id, role, verified,
     fail_count, locked_until, totp_enabled) = rows[0]

    # Check lockout before bcrypt (no timing oracle on locked accounts).
    if locked_until:
        now = datetime.now(timezone.utc)
        lu = locked_until if locked_until.tzinfo else locked_until.replace(tzinfo=timezone.utc)
        if now < lu:
            return None, "locked"

    if not verify_password(password, pw_hash or ""):
        new_fail = (fail_count or 0) + 1
        if new_fail >= _MAX_LOGIN_ATTEMPTS:
            db.execute_query(
                "UPDATE saas_users SET failed_login_attempts = %s, "
                "locked_until = NOW() + make_interval(mins => %s) WHERE id = %s",
                (new_fail, _LOCKOUT_MINUTES, uid),
            )
        else:
            db.execute_query(
                "UPDATE saas_users SET failed_login_attempts = %s WHERE id = %s",
                (new_fail, uid),
            )
        return None, "invalid_credentials"

    db.execute_query(
        "UPDATE saas_users SET failed_login_attempts = 0, locked_until = NULL WHERE id = %s",
        (uid,),
    )
    if not verified:
        return None, "unverified"
    if totp_enabled:
        return None, "totp_required"
    return {"id": uid, "username": uname, "email": email,
            "artist_id": artist_id, "role": role}, None
