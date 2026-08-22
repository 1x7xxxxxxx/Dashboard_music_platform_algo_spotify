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


def get_current_user(token: str = Depends(oauth2_scheme),
                     db: PostgresHandler = Depends(get_db)) -> dict:
    """Decode the JWT, then confirm the account still exists and still authorises it.

    Signature-valid is not the same as still-valid (R24, 2026-08-22). Before this,
    the only questions asked were "does it verify" and "does it carry a sub", both
    answerable from the token alone — so deactivating an account left its holder with
    up to 24 h of API access, and changing a compromised password evicted nobody.

    Three things are re-read from `saas_users` on every request:

      * the row exists — a deleted account's token stopped meaning anything;
      * `active` is true — this is what `admin.py` sets to FALSE;
      * `token_version` is not ahead of the token's `tv` claim — bumped by a password
        change and by a deactivation (migration 072).

    A token minted before 072 carries no `tv`; it is read as 0 and matches the column
    default, so deploying this did not sign anyone out.

    Cost: one primary-key-indexed lookup per request. That is the price of revocation
    on a stateless token, and the alternative — a denylist — needs a store this
    deployment does not have (ADR-002).

    When the database is unreachable, this FAILS CLOSED with 503 rather than trusting
    the token: an outage must not become a window in which revocation does not apply.
    """
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

    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable")
    rows = db.fetch_query(
        "SELECT active, token_version, role, artist_id FROM saas_users "
        "WHERE username = %s LIMIT 1",
        (payload["sub"],),
    )
    if not rows:
        raise credentials_exc
    active, token_version, role, artist_id = rows[0]
    if not active or (token_version or 0) > int(payload.get("tv", 0)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # The row wins over the claim: a role or scope changed after the token was issued
    # must take effect now, not at expiry. Same reason the claims are re-read at all.
    payload["role"] = role
    payload["artist_id"] = artist_id
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
