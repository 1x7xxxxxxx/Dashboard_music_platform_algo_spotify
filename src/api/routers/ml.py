"""ML prediction endpoints.

GET /ml/predictions — latest model scores per song for the authenticated artist
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.deps import get_db, get_current_user
from src.database.postgres_handler import PostgresHandler

router = APIRouter(prefix="/ml", tags=["ml"])


class MLPrediction(BaseModel):
    song: str
    score: float
    tier: str
    predicted_at: Optional[str] = None


@router.get("/predictions", response_model=list[MLPrediction], summary="ML song predictions")
def get_predictions(
    limit: int = Query(20, ge=1, le=100),
    db: PostgresHandler = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    artist_id = user.get("artist_id")
    if artist_id:
        df = db.fetch_df(
            """
            SELECT song, score, tier, predicted_at::text AS predicted_at
            FROM ml_song_predictions
            WHERE artist_id = %s
            ORDER BY score DESC, predicted_at DESC
            LIMIT %s
            """,
            (artist_id, limit),
        )
    else:
        df = db.fetch_df(
            """
            SELECT song, score, tier, predicted_at::text AS predicted_at
            FROM ml_song_predictions
            ORDER BY score DESC, predicted_at DESC
            LIMIT %s
            """,
            (limit,),
        )

    if df.empty:
        return []
    return [
        MLPrediction(
            song=r["song"],
            score=float(r["score"]),
            tier=r["tier"],
            predicted_at=r.get("predicted_at"),
        )
        for _, r in df.iterrows()
    ]
