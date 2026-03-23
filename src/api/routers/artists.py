"""Artist endpoints.

GET /artists/me  — current user's artist profile
GET /artists     — all artists (admin only)
"""
from fastapi import APIRouter, Depends
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
    artist_id = user.get("artist_id")
    if not artist_id:
        return {"role": "admin", "artist_id": None}
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
