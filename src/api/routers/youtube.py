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
    # The per-day stats (view_count/like_count/comment_count + artist_id) live in
    # youtube_video_stats; the title lives in youtube_videos. We read stats from the
    # stats table (those columns exist in BOTH the canonical schema and prod) and
    # LEFT JOIN youtube_videos only for the title. NB: prod's youtube_videos drifted
    # to also carry the counts, but init_db.sql/youtube_schema.py do not — querying
    # youtube_videos.view_count therefore 500s in CI/fresh installs. Source the counts
    # from youtube_video_stats to stay schema-portable.
    # artist_id is None only for admin (all-tenants); non-admins are always scoped.
    _select = """
        SELECT s.video_id, v.title,
               s.view_count AS views, s.like_count AS likes, s.comment_count AS comments,
               s.collected_at::text AS collected_at
        FROM youtube_video_stats s
        LEFT JOIN youtube_videos v ON v.video_id = s.video_id
    """
    if artist_id is not None:
        df = db.fetch_df(
            _select + " WHERE s.artist_id = %s ORDER BY s.collected_at DESC LIMIT %s",
            (artist_id, limit),
        )
    else:
        df = db.fetch_df(
            _select + " ORDER BY s.collected_at DESC LIMIT %s",
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
