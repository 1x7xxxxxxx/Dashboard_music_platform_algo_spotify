"""ML prediction endpoints.

GET /ml/predictions — latest model probabilities per song for the authenticated artist
"""
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.deps import get_db, require_artist_scope
from src.database.postgres_handler import PostgresHandler

router = APIRouter(prefix="/ml", tags=["ml"])

# S4A "Total" summary row — excluded from every song-level query (CLAUDE.md).
_ARTIST_NAME_FILTER = "1x7xxxxxxx"


class MLPrediction(BaseModel):
    song: str
    prediction_date: Optional[str] = None
    dw_probability: Optional[float] = None
    rr_probability: Optional[float] = None
    radio_probability: Optional[float] = None


def _f(v) -> Optional[float]:
    """Coerce a DB double (NULL → NaN once in a DataFrame) to float | None."""
    return float(v) if v is not None and not pd.isna(v) else None


@router.get("/predictions", response_model=list[MLPrediction], summary="ML song predictions")
def get_predictions(
    limit: int = Query(20, ge=1, le=100),
    db: PostgresHandler = Depends(get_db),
    artist_id: Optional[int] = Depends(require_artist_scope),
):
    # ml_song_predictions stores the three algo probabilities (dw/rr/radio) keyed by
    # song + prediction_date — there is no persisted "score"/"tier" (the /20 score is a
    # dashboard-only presentation). Return the latest row per song. artist_id is None
    # only for admin tokens (all tenants); non-admins are always scoped.
    conds = ["song NOT ILIKE %s"]
    params: list = [f"%{_ARTIST_NAME_FILTER}%"]
    if artist_id is not None:
        conds.append("artist_id = %s")
        params.append(artist_id)
    where = " AND ".join(conds)

    df = db.fetch_df(
        f"""
        SELECT song, prediction_date::text AS prediction_date,
               dw_probability, rr_probability, radio_probability
        FROM (
            SELECT DISTINCT ON (song) song, prediction_date,
                   dw_probability, rr_probability, radio_probability
            FROM ml_song_predictions
            WHERE {where}
            ORDER BY song, prediction_date DESC
        ) latest
        ORDER BY dw_probability DESC NULLS LAST
        LIMIT %s
        """,
        tuple(params) + (limit,),
    )
    if df.empty:
        return []
    return [
        MLPrediction(
            song=r["song"],
            prediction_date=r.get("prediction_date"),
            dw_probability=_f(r.get("dw_probability")),
            rr_probability=_f(r.get("rr_probability")),
            radio_probability=_f(r.get("radio_probability")),
        )
        for _, r in df.iterrows()
    ]
