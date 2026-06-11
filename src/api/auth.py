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
