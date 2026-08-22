"""Artist endpoints.

GET /artists/me  — current user's artist profile
GET /artists     — all artists (admin only)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.deps import get_db, get_current_user, require_admin
from src.database.postgres_handler import PostgresHandler

router = APIRouter(prefix="/artists", tags=["artists"])


class ArtistOut(BaseModel):
    id: int
    name: str
    active: bool


@router.get("/me", summary="Current user — artist profile or admin info")
def get_me(db: PostgresHandler = Depends(get_db), user: dict = Depends(get_current_user)):
    # Decide on the ROLE, never on a falsy id. `if not artist_id` is exactly the
    # test `require_artist_scope` was written to delete (see api/deps.py): a
    # non-admin token whose artist_id is missing, None or 0 answered "role: admin".
    # Harmless on this endpoint — it returns no data — and the same shape that leaked
    # every tenant on the data routers, which is reason enough not to leave a copy.
    if user.get("role") == "admin":
        return {"role": "admin", "artist_id": None}
    artist_id = user.get("artist_id")
    if artist_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Token carries no artist scope")
    df = db.fetch_df(
        "SELECT id, name, active FROM saas_artists WHERE id = %s",
        (artist_id,),
    )
    if df.empty:
        return {"id": artist_id, "name": "unknown", "active": False}
    row = df.iloc[0]
    return ArtistOut(id=int(row["id"]), name=row["name"], active=bool(row["active"]))


@router.get("", response_model=list[ArtistOut], summary="List all artists (admin)")
def list_artists(
    db: PostgresHandler = Depends(get_db),
    _user: dict = Depends(require_admin),
):
    df = db.fetch_df("SELECT id, name, active FROM saas_artists ORDER BY id")
    return [ArtistOut(id=int(r["id"]), name=r["name"], active=bool(r["active"])) for _, r in df.iterrows()]
