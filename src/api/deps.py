"""FastAPI dependencies: DB session and current-user extraction."""
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from src.api.auth import decode_token
from src.dashboard.utils import get_db_connection
from src.database.postgres_handler import PostgresHandler

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_db() -> Generator[PostgresHandler, None, None]:
    """Open a DB connection, yield it, then close it — one per request."""
    db = get_db_connection()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Decode the JWT and return its payload as a dict."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if not payload.get("sub"):
            raise credentials_exc
    except JWTError:
        raise credentials_exc
    return payload


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Guard: raise 403 unless the token carries role=admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
