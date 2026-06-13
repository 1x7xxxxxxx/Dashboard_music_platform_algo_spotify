"""YouTube video stats endpoints.

GET /youtube/videos — latest collected video stats for the authenticated artist
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.deps import get_db, require_artist_scope
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
    artist_id: Optional[int] = Depends(require_artist_scope),
):
    # youtube_videos is the per-video catalog (one row/video) carrying title + the
    # latest view/like/comment counts. youtube_video_stats is the per-day snapshot
    # series with NO title column and view_count/like_count/comment_count names — it
    # was the source of the old 500 (SELECT views/likes/comments/title all wrong).
    # artist_id is None only for admin (all-tenants); non-admins are always scoped.
    _select = """
        SELECT video_id, title,
               view_count AS views, like_count AS likes, comment_count AS comments,
               collected_at::text AS collected_at
        FROM youtube_videos
    """
    if artist_id is not None:
        df = db.fetch_df(
            _select + " WHERE artist_id = %s ORDER BY collected_at DESC, view_count DESC LIMIT %s",
            (artist_id, limit),
        )
    else:
        df = db.fetch_df(
            _select + " ORDER BY collected_at DESC, view_count DESC LIMIT %s",
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
