"""Write a defect into `app_error_log`, and read the open ones back.

Type: Utility
Uses: error_fingerprint, safe_error
Triggers: dashboard.utils.error_alert, alert_monitor.check_app_errors, tools/error_inbox.py
Depends on: app_error_log (migration 083)
Persists in: app_error_log

Separated from `error_alert` on purpose: that module lives in the dashboard package and
reaches into `st.session_state`, so nothing outside Streamlit could reuse it — and the
nightly monitor, the API and the tests all need to read or write the same registry.
Everything here takes its inputs explicitly and touches no framework.
"""
from __future__ import annotations

import traceback
from typing import Any, Optional

_TB_CHARS = 4000


def record_error(db, page: Optional[str], exc: BaseException,
                 artist_id: Optional[int] = None,
                 environment: str = "unknown") -> Optional[str]:
    """Upsert ONE row per fingerprint. Returns it, or None if nothing was written.

    A new occurrence REOPENS a resolved defect (`resolved_at = NULL`). Seeing something
    come back after it was closed is the most useful thing this table can tell you, and
    keeping it closed would lose it in silence.
    """
    from src.utils.error_fingerprint import fingerprint, origin_frame
    from src.utils.safe_error import redact

    if db is None:
        return None
    fp = fingerprint(exc)
    tb = redact(''.join(
        traceback.format_exception(type(exc), exc, exc.__traceback__))[-_TB_CHARS:])
    db.execute_query(
        """
        INSERT INTO app_error_log (fingerprint, exc_type, message, page, origin,
                                   artist_id, environment, traceback)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fingerprint) DO UPDATE SET
            last_seen   = NOW(),
            occurrences = app_error_log.occurrences + 1,
            message     = EXCLUDED.message,
            traceback   = EXCLUDED.traceback,
            page        = EXCLUDED.page,
            resolved_at = NULL
        """,
        (fp, type(exc).__name__[:120], redact(exc)[:500], (page or '?')[:120],
         (origin_frame(exc) or 'unknown')[:120], artist_id, environment[:20], tb),
    )
    return fp


def open_errors(db, limit: int = 20) -> list[dict[str, Any]]:
    """Unresolved defects, most recently seen first — for the nightly report."""
    if db is None:
        return []
    rows = db.fetch_query(
        """
        SELECT fingerprint, exc_type, page, origin, environment, occurrences,
               first_seen, last_seen
        FROM app_error_log
        WHERE resolved_at IS NULL
        ORDER BY last_seen DESC
        LIMIT %s
        """,
        (limit,),
    )
    return [
        {'fingerprint': r[0], 'exc_type': r[1], 'page': r[2], 'origin': r[3],
         'environment': r[4], 'occurrences': r[5], 'first_seen': r[6],
         'last_seen': r[7]}
        for r in rows or []
    ]


def open_errors_for_alert(limit: int = 15) -> list[dict[str, Any]]:
    """Les défauts ouverts, mis en forme pour le mail du soir. Ne lève jamais.

    Vit ici et non dans `alert_monitor.py` pour deux raisons. La première est mécanique :
    le DAG porte un cliquet de longueur qui ne monte jamais
    (`tests/test_a_file_only_gets_shorter.py`), et ajouter un sujet à un fichier de
    2 700 lignes oblige à en alléger — c'est précisément ce que le cliquet existe pour
    forcer. La seconde est de fond : cette fonction ne fait aucun ordonnancement, elle
    lit le registre et calcule un âge. Elle appartient au registre.

    Délibérément compact : classe d'exception, où, combien de fois, depuis quand. **Pas
    de traceback** — celui-ci vit dans `make error-inbox`, et un mail de nuit qui en
    porte trois cesse d'être lu, ce qui est comment le constat de sauvegarde hors-site
    est passé près de l'oubli.

    ⚠️ Rend UNE ligne `UNAVAILABLE` quand le registre est illisible, jamais une liste
    vide : une liste vide se lit « aucun défaut ouvert », soit l'inverse de la vérité.
    """
    import logging
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)
    db = None
    try:
        from src.database.postgres_handler import PostgresHandler

        db = PostgresHandler.from_env_or_config()
        out: list[dict[str, Any]] = []
        for e in open_errors(db, limit=limit):
            age_h = None
            try:
                age_h = (datetime.now(timezone.utc)
                         - e['first_seen']).total_seconds() / 3600
            except (TypeError, ValueError):
                pass
            out.append({
                'fingerprint': e['fingerprint'][:12],
                'exc_type': e['exc_type'],
                'origin': e['origin'] or '?',
                'page': e['page'] or '—',
                'environment': e['environment'],
                'occurrences': e['occurrences'],
                'age': f"{age_h:.0f} h" if age_h is not None and age_h < 48
                       else (f"{age_h / 24:.0f} j" if age_h is not None else '?'),
            })
        return out
    except Exception as exc:  # noqa: BLE001 — même contrat que les autres contrôles
        logger.error("registre des erreurs illisible : %s", type(exc).__name__)
        return [{'fingerprint': '—', 'exc_type': 'UNAVAILABLE',
                 'origin': f'registre illisible : {type(exc).__name__}',
                 'page': '—', 'environment': '—', 'occurrences': 0, 'age': '?'}]
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:  # noqa: BLE001
                pass
