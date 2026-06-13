"""POST /auth/token — issue a JWT from dashboard credentials.

Authenticates against the ``saas_users`` table (same accounts as the Streamlit
dashboard: username OR email + bcrypt password), so the API works in prod where there
is no config.yaml. Shares the dashboard's brute-force lockout; refuses 2FA accounts.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from src.api.auth import authenticate_api_user, create_access_token
from src.api.deps import get_db
from src.database.postgres_handler import PostgresHandler

router = APIRouter(prefix="/auth", tags=["auth"])


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    artist_id: int | None = None


# Non-credential failure reasons → explicit status + message (kept distinct from the
# generic 401 so a legit user understands a lockout / unverified / 2FA situation).
_REASON_STATUS = {
    "locked": (status.HTTP_429_TOO_MANY_REQUESTS,
               "Account locked after too many failed attempts. Try again later."),
    "unverified": (status.HTTP_403_FORBIDDEN,
                   "Email not verified — verify your email before using the API."),
    "totp_required": (status.HTTP_403_FORBIDDEN,
                      "2FA-enabled accounts cannot use the token endpoint (it would "
                      "bypass your second factor). Use the dashboard."),
}


@router.post("/token", response_model=Token, summary="Login — obtain a JWT")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: PostgresHandler = Depends(get_db),
):
    """OAuth2 password flow against saas_users (username OR email + bcrypt)."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable")

    user, reason = authenticate_api_user(db, form_data.username, form_data.password)
    if user is None:
        if reason in _REASON_STATUS:
            code, detail = _REASON_STATUS[reason]
            raise HTTPException(status_code=code, detail=detail,
                                headers={"WWW-Authenticate": "Bearer"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        {"sub": user["username"], "role": user["role"], "artist_id": user["artist_id"]}
    )
    return Token(access_token=token, token_type="bearer",
                 role=user["role"], artist_id=user["artist_id"])
