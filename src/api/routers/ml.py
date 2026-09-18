"""ML prediction endpoints.

GET /ml/predictions — latest model probabilities per song for the authenticated artist
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.deps import get_db, require_artist_scope
from src.database.postgres_handler import PostgresHandler

router = APIRouter(prefix="/ml", tags=["ml"])

# S4A "Total" summary row — excluded from every song-level query (CLAUDE.md).
from src.utils.artist_name_filter import (
    ARTIST_NAME_FILTER as _ARTIST_NAME_FILTER,
)


class MLPrediction(BaseModel):
    song: str
    prediction_date: Optional[str] = None
    dw_probability: Optional[float] = None
    rr_probability: Optional[float] = None
    radio_probability: Optional[float] = None


def _f(v) -> Optional[float]:
    """Coerce a DB double (NULL → NaN once in a DataFrame) to float | None.

    ⚠️ **Sans pandas, et c'est un correctif de coût mesuré.** Ce module portait
    `import pandas as pd` au niveau module pour ce SEUL `pd.isna(v)`, et il était le
    seul importateur de pandas de tout `src/api/`. Mesuré en alternance sur trois
    tirages (`python -X importtime -c "import src.api.main"`) : pandas pèse
    **~300 ms sur ~800**, soit près de **40 % du temps d'import de l'application**.
    C'est payé à chaque démarrage de PROCESSUS — conteneur, déploiement, reprise après
    OOM — jamais amorti par le trafic.

    L'équivalence n'est pas supposée : les deux formes ont été confrontées sur 16 cas
    (`None`, entiers, `Decimal`, `±inf`, `float('nan')`, `np.nan`, `np.float64('nan')`,
    `pd.NA`, `pd.NaT`, `np.int64`) — **0 divergence**. `pd.NA` et `NaT` lèvent sur
    `float()`, d'où le `except`, et `NaN != NaN` fait le reste sans aucune dépendance.
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):   # pd.NA, pd.NaT, tout objet non convertible
        return None
    return f if f == f else None      # NaN est le seul float différent de lui-même


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
