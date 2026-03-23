"""YouTube video stats endpoints.

GET /youtube/videos — latest collected video stats for the authenticated artist
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.deps import get_db, get_current_user
from src.database.postgres_handler import PostgresHandler

router = APIRouter(prefix="/youtube", tags=["youtube"])


class VideoStats(BaseModel):
    video_id: str
    title: Optional[str] = None
    views: int
    likes: int
    comments: int
    collected_at: Optional[str] = None


@router.get("/videos", response_model=list[VideoStats], summary="Latest YouTube video stats")
def get_videos(
    limit: int = Query(50, ge=1, le=200),
    db: PostgresHandler = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    artist_id = user.get("artist_id")
    if artist_id:
        df = db.fetch_df(
            """
            SELECT video_id, title, views, likes, comments, collected_at::text AS collected_at
            FROM youtube_video_stats
            WHERE artist_id = %s
            ORDER BY collected_at DESC
            LIMIT %s
            """,
            (artist_id, limit),
        )
    else:
        df = db.fetch_df(
            """
            SELECT video_id, title, views, likes, comments, collected_at::text AS collected_at
            FROM youtube_video_stats
            ORDER BY collected_at DESC
            LIMIT %s
            """,
            (limit,),
        )

    if df.empty:
        return []
    return [
        VideoStats(
            video_id=r["video_id"],
            title=r.get("title"),
            views=int(r.get("views") or 0),
            likes=int(r.get("likes") or 0),
            comments=int(r.get("comments") or 0),
            collected_at=r.get("collected_at"),
        )
        for _, r in df.iterrows()
    ]
