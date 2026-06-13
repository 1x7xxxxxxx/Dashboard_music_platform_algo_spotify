"""FastAPI dependencies: DB session and current-user extraction."""
from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from src.api.auth import decode_token
from src.dashboard.utils import get_db_connection
from src.database.postgres_handler import PostgresHandler

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_db() -> Generator[PostgresHandler, None, None]:
    """Open a DB connection, yield it, then close it — one per request.

    get_db_connection() returns None when Postgres is unreachable; the teardown must
    not crash on that (else an auth 401 — which never touches the DB — turns into a
    500 'NoneType has no attribute close'). Endpoints that actually query guard their
    own None handling."""
    db = get_db_connection()
    try:
        yield db
    finally:
        if db is not None:
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


def require_artist_scope(user: dict = Depends(get_current_user)) -> Optional[int]:
    """Resolve the tenant scope for a data request — the single source of truth for
    'whose data may this token read'.

    - role=admin            → returns None  → caller reads ALL tenants (by design).
    - non-admin with artist_id → returns that int → caller MUST filter `WHERE artist_id = %s`.
    - non-admin WITHOUT artist_id → 403.

    Rationale: data routers previously used `if artist_id:` (truthiness) as an
    implicit 'is admin' test, so a non-admin token whose artist_id claim was missing
    / None / 0 silently fell through to the unfiltered (all-tenants) branch — a
    cross-tenant leak. Scope must be decided by ROLE, never by a falsy id.
    """
    if user.get("role") == "admin":
        return None
    artist_id = user.get("artist_id")
    if artist_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Token carries no artist scope")
    return artist_id
