"""Home KPI summary endpoint.

GET /kpis — single-call snapshot of the most recent data per source for the
             authenticated artist (or across all artists for admin).
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.deps import get_db, get_current_user
from src.database.postgres_handler import PostgresHandler

router = APIRouter(prefix="/kpis", tags=["kpis"])

_ARTIST_NAME_FILTER = "1x7xxxxxxx"


class KPISummary(BaseModel):
    spotify_streams_7d: Optional[int] = None
    youtube_views_latest: Optional[int] = None
    soundcloud_plays_latest: Optional[int] = None
    instagram_followers_latest: Optional[int] = None
    ml_top_song: Optional[str] = None
    ml_top_score: Optional[float] = None


def _first_val(db: PostgresHandler, query: str, params: tuple, col: str):
    """Execute query and return the first value of `col`, or None."""
    df = db.fetch_df(query, params)
    if df.empty or df.iloc[0][col] is None:
        return None
    return df.iloc[0][col]


@router.get("", response_model=KPISummary, summary="Home KPI snapshot")
def get_kpis(
    db: PostgresHandler = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    aid = user.get("artist_id")
    p_aid = (aid,) if aid else ()
    filt = "AND artist_id = %s" if aid else ""

    # Spotify — streams last 7 days
    raw_spotify = _first_val(
        db,
        f"""
        SELECT COALESCE(SUM(streams), 0) AS total
        FROM s4a_song_timeline
        WHERE date >= CURRENT_DATE - 7
          AND song NOT ILIKE %s {filt}
        """,
        (f"%{_ARTIST_NAME_FILTER}%",) + p_aid,
        "total",
    )
    spotify_7d = int(raw_spotify) if raw_spotify else None

    # YouTube — views from most recent collected row
    raw_yt = _first_val(
        db,
        f"""
        SELECT views FROM youtube_video_stats
        WHERE 1=1 {filt}
        ORDER BY collected_at DESC LIMIT 1
        """,
        p_aid,
        "views",
    )
    yt_views = int(raw_yt) if raw_yt else None

    # SoundCloud — plays from most recent row
    raw_sc = _first_val(
        db,
        f"""
        SELECT plays FROM soundcloud_tracks
        WHERE 1=1 {filt}
        ORDER BY collected_at DESC LIMIT 1
        """,
        p_aid,
        "plays",
    )
    sc_plays = int(raw_sc) if raw_sc else None

    # Instagram — latest follower count
    raw_ig = _first_val(
        db,
        f"""
        SELECT followers_count FROM instagram_account_stats
        WHERE 1=1 {filt}
        ORDER BY collected_at DESC LIMIT 1
        """,
        p_aid,
        "followers_count",
    )
    ig_followers = int(raw_ig) if raw_ig else None

    # ML — top song by score
    df_ml = db.fetch_df(
        f"""
        SELECT song, score FROM ml_song_predictions
        WHERE 1=1 {filt}
        ORDER BY score DESC LIMIT 1
        """,
        p_aid,
    )
    ml_song = df_ml.iloc[0]["song"] if not df_ml.empty else None
    ml_score = float(df_ml.iloc[0]["score"]) if not df_ml.empty else None

    return KPISummary(
        spotify_streams_7d=spotify_7d,
        youtube_views_latest=yt_views,
        soundcloud_plays_latest=sc_plays,
        instagram_followers_latest=ig_followers,
        ml_top_song=ml_song,
        ml_top_score=ml_score,
    )
