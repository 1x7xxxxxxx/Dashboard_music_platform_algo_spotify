"""Streaming history endpoints (Spotify for Artists data).

GET /streams/timeline  — paginated daily stream counts per song
GET /streams/summary   — aggregate totals for the authenticated artist
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.deps import get_db, require_artist_scope
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


def _artist_clause(artist_id: Optional[int]) -> tuple[str, tuple]:
    # artist_id is None only for admin (all-tenants); non-admins are always scoped.
    if artist_id is None:
        return "", ()
    return "AND artist_id = %s", (artist_id,)


@router.get("/timeline", response_model=list[StreamPoint], summary="Daily stream timeline")
def get_timeline(
    song: Optional[str] = Query(None, description="Partial song name filter (ILIKE)"),
    limit: int = Query(100, ge=1, le=1000),
    db: PostgresHandler = Depends(get_db),
    aid: Optional[int] = Depends(require_artist_scope),
):
    artist_frag, params = _artist_clause(aid)
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
    aid: Optional[int] = Depends(require_artist_scope),
):
    artist_frag, params = _artist_clause(aid)
    # LE TOTAL VIENT DE LA COUCHE OR (ADR-019), le reste de la table de fait.
    #
    # `SUM(streams)` était ici la deuxième définition du total Spotify : la couche or
    # déduplique d'abord par (date, titre) et somme le MAX — deux imports du même jour
    # ne doivent pas doubler les écoutes. Les deux s'accordent aujourd'hui (165 065
    # mesuré par les deux chemins le 2026-09-11) parce qu'un index unique interdit le
    # doublon ; le jour où il saute, l'API et le dashboard donnent deux nombres, et
    # c'est l'API — un AUTRE processus — qui diverge en silence.
    #
    # `unique_songs` et `latest_date` ne sont pas des métriques métier : un décompte
    # de titres et une date de dernière ligne n'ont pas de définition à centraliser.
    # Ils restent sur le fait, et la ligne du filtre « Total » avec eux.
    df = db.fetch_df(
        f"""
        SELECT
            (SELECT COALESCE(SUM(total), 0) FROM v_platform_totals
              WHERE platform = 'spotify' {artist_frag}) AS total_streams,
            COUNT(DISTINCT song)              AS unique_songs,
            MAX(date)::text                   AS latest_date
        FROM s4a_song_timeline
        WHERE song NOT ILIKE %s {artist_frag}
        """,
        params + (f"%{_ARTIST_NAME_FILTER}%",) + params,
    )
    row = df.iloc[0] if not df.empty else {}
    return StreamSummary(
        total_streams=int(row.get("total_streams") or 0),
        unique_songs=int(row.get("unique_songs") or 0),
        latest_date=row.get("latest_date"),
    )
