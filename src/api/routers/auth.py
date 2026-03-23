"""POST /auth/token — issue a JWT from dashboard credentials.

Credentials are read from the same config.yaml used by the Streamlit dashboard
(``auth.credentials.usernames``).  Each user entry must have a bcrypt-hashed
``password`` field (same format as streamlit-authenticator).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from src.api.auth import verify_password, create_access_token
from src.utils.config_loader import config_loader

router = APIRouter(prefix="/auth", tags=["auth"])


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    artist_id: int | None = None


@router.post("/token", response_model=Token, summary="Login — obtain a JWT")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Standard OAuth2 password flow.  Send ``username`` + ``password`` as form data."""
    config = config_loader.load()
    auth_cfg = config.get("auth")
    if not auth_cfg:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication not configured (no 'auth' section in config.yaml)",
        )

    users: dict = auth_cfg.get("credentials", {}).get("usernames", {})
    user_data = users.get(form_data.username)

    if not user_data or not verify_password(form_data.password, user_data.get("password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role: str = user_data.get("role", "artist")
    artist_id: int | None = user_data.get("artist_id")

    token = create_access_token(
        {"sub": form_data.username, "role": role, "artist_id": artist_id}
    )
    return Token(access_token=token, token_type="bearer", role=role, artist_id=artist_id)
