"""ML prediction endpoints.

GET /ml/predictions — latest model scores per song for the authenticated artist
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.deps import get_db, require_artist_scope
from src.database.postgres_handler import PostgresHandler

router = APIRouter(prefix="/ml", tags=["ml"])


class MLPrediction(BaseModel):
    song: str
    score: float
    tier: str
    predicted_at: Optional[str] = None


# ⚠️ KNOWN-BROKEN (flagged 2026-06-11 pre-deploy audit): this query references columns
# that DO NOT EXIST on ml_song_predictions — there is no `score`, no `tier`, and the date
# column is `prediction_date` (not `predicted_at`). The table stores `dw_probability`,
# `rr_probability`, `radio_probability`, ... and the /20 score is computed in the dashboard
# (see _compute_score_20), not persisted. This endpoint 500s on every call. Fixing it
# requires an API-contract decision (return the probabilities, or compute a score) — left
# for a reviewed change before the FastAPI surface is exposed. Tracked in DEVLOG.
@router.get("/predictions", response_model=list[MLPrediction], summary="ML song predictions")
def get_predictions(
    limit: int = Query(20, ge=1, le=100),
    db: PostgresHandler = Depends(get_db),
    artist_id: Optional[int] = Depends(require_artist_scope),
):
    # artist_id is None only for admin (all-tenants); non-admins are always scoped.
    if artist_id is not None:
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
