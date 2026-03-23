"""Streaming history endpoints (Spotify for Artists data).

GET /streams/timeline  — paginated daily stream counts per song
GET /streams/summary   — aggregate totals for the authenticated artist
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.deps import get_db, get_current_user
from src.database.postgres_handler import PostgresHandler

router = APIRouter(prefix="/streams", tags=["streams"])

# Must be excluded from all S4A queries — see CLAUDE.md
_ARTIST_NAME_FILTER = "1x7xxxxxxx"


class StreamPoint(BaseModel):
    date: str
    song: str
    streams: int


class StreamSummary(BaseModel):
    total_streams: int
    unique_songs: int
    latest_date: Optional[str] = None


def _artist_clause(user: dict) -> tuple[str, tuple]:
    artist_id = user.get("artist_id")
    if artist_id is None:
        return "", ()
    return "AND artist_id = %s", (artist_id,)


@router.get("/timeline", response_model=list[StreamPoint], summary="Daily stream timeline")
def get_timeline(
    song: Optional[str] = Query(None, description="Partial song name filter (ILIKE)"),
    limit: int = Query(100, ge=1, le=1000),
    db: PostgresHandler = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    artist_frag, params = _artist_clause(user)
    song_frag = ""
    if song:
        song_frag = "AND song ILIKE %s"
        params = params + (f"%{song}%",)

    df = db.fetch_df(
        f"""
        SELECT date::text AS date, song, streams
        FROM s4a_song_timeline
        WHERE song NOT ILIKE %s
          {artist_frag}
          {song_frag}
        ORDER BY date DESC
        LIMIT %s
        """,
        (f"%{_ARTIST_NAME_FILTER}%",) + params + (limit,),
    )
    if df.empty:
        return []
    return [StreamPoint(date=r["date"], song=r["song"], streams=int(r["streams"])) for _, r in df.iterrows()]


@router.get("/summary", response_model=StreamSummary, summary="Aggregate stream totals")
def get_summary(
    db: PostgresHandler = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    artist_frag, params = _artist_clause(user)
    df = db.fetch_df(
        f"""
        SELECT
            COALESCE(SUM(streams), 0)        AS total_streams,
            COUNT(DISTINCT song)              AS unique_songs,
            MAX(date)::text                   AS latest_date
        FROM s4a_song_timeline
        WHERE song NOT ILIKE %s {artist_frag}
        """,
        (f"%{_ARTIST_NAME_FILTER}%",) + params,
    )
    row = df.iloc[0] if not df.empty else {}
    return StreamSummary(
        total_streams=int(row.get("total_streams") or 0),
        unique_songs=int(row.get("unique_songs") or 0),
        latest_date=row.get("latest_date"),
    )
