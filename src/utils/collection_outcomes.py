"""Distinguer une collecte qui vient de casser d'une collecte bloquée depuis des mois.

Type: Utility
Uses: etl_run_log, saas_artists (collection_failures only — the rest is pure)
Depends on: a PostgresHandler-like `db` with fetch_query
Triggers: airflow/dags/alert_monitor.py (check_collection_outcomes + le rendu de l'e-mail),
          src/dashboard/views/admin_collection.py (R418 — the same rows, on screen)
Persists in: nothing

Why this module exists
----------------------
Measured in production on 2026-09-10: tenant 12 had failed its Meta collection
**every single night since 2026-06-19** — 93 consecutive nights, always the same
cause: `(#200) Ad account owner has NOT grant ads_management or ads_read permission`.
No run can clear that: it names a human gesture to be made on Meta's side.

The alert was not wrong to report it. It was wrong to report it *identically* on
night 1 and on night 93. A subject line that never changes stops being read, and the
night it finally changes nobody sees it. So the ledger's age is measured and shown,
and the subject names what broke recently while merely counting what has been stuck.

Nothing is silenced: a long-standing block keeps a full row in the body, with its
age and its cause.

These two decisions live here rather than inline in the DAG because a DAG module
cannot be imported outside its container — a rule the repo learned the hard way:
a threshold written inside a DAG is a threshold no test ever exercises.
"""
from __future__ import annotations

# Une seule nuit d'échec = ce qui vient de casser. C'est la seule valeur qu'une
# exécution puisse encore corriger, donc la seule qui mérite la ligne d'objet.
FRESH_NIGHTS = 1


def failure_age_nights(problem: dict) -> int:
    """Nights failed since the last success — 1 when it broke tonight."""
    try:
        return max(1, int(problem.get('failing_nights') or 1))
    except (TypeError, ValueError):
        # Une ancienneté illisible se lit « cette nuit » : on préfère alerter à tort
        # que classer en silence un vrai incident parmi les blocages installés.
        return 1


def is_long_standing(problem: dict) -> bool:
    return failure_age_nights(problem) > FRESH_NIGHTS


def split_by_age(problems: list[dict]) -> tuple[list[dict], list[dict]]:
    """(ce qui vient de casser, ce qui est bloqué de longue date)."""
    fresh = [p for p in problems if not is_long_standing(p)]
    stuck = [p for p in problems if is_long_standing(p)]
    return fresh, stuck


def describe_failure_age(problem: dict) -> str:
    """La phrase montrée dans la colonne « Depuis » de l'e-mail."""
    nights = failure_age_nights(problem)
    if nights <= FRESH_NIGHTS:
        return "cette nuit"
    last = problem.get('last_success')
    when = str(last)[:10] if last else "jamais"
    return f"{nights} nuits d'affilée · dernier succès {when}"


# One nightly cycle plus margin — a single missed run is not news.
WINDOW_H = 36

_LEDGER_SQL = """
    WITH latest AS (
        SELECT DISTINCT ON (e.artist_id, e.platform)
               e.artist_id, e.platform, e.dag_id,
               e.status, e.error_message, e.started_at
        FROM etl_run_log e
        WHERE e.started_at > now() - make_interval(hours => %s)
          AND e.artist_id IS NOT NULL
        ORDER BY e.artist_id, e.platform, e.started_at DESC
    )
    SELECT l.artist_id, a.name, l.platform, l.dag_id,
           l.status, l.error_message, l.started_at,
           (SELECT max(s.started_at) FROM etl_run_log s
             WHERE s.artist_id = l.artist_id AND s.platform = l.platform
               AND s.status = 'success') AS last_success,
           (SELECT count(DISTINCT s.started_at::date) FROM etl_run_log s
             WHERE s.artist_id = l.artist_id AND s.platform = l.platform
               AND s.status IN ('failed', 'partial')
               AND s.started_at > COALESCE(
                   (SELECT max(s2.started_at) FROM etl_run_log s2
                     WHERE s2.artist_id = l.artist_id
                       AND s2.platform = l.platform
                       AND s2.status = 'success'),
                   '-infinity'::timestamp)) AS failing_nights
    FROM latest l
    JOIN saas_artists a ON a.id = l.artist_id
    ORDER BY l.artist_id, l.platform
"""


def collection_failures(db, window_h: int = WINDOW_H) -> list[dict]:
    """The LAST outcome per (tenant, platform) inside the window, kept when it failed.

    One reader for two surfaces (R418): the evening mail and the admin screen. The owner
    deletes the mail, so the screen must show the SAME rows — a second query would drift.

    Raises on a read failure. « Could not read » and « nothing failed » must not look
    alike: the DAG turns the exception into a 'check could not run' row, the view into
    an error. A tenant that failed at 03:00 and succeeded on a re-run at 09:00 is not a
    problem — taking the latest row is what makes that true. No active/human filter: a
    deactivated tenant whose collection still runs and fails is still a finding.
    """
    problems = []
    for (artist_id, name, platform, dag_id, status, error_message, started_at,
         last_success, failing_nights) in db.fetch_query(_LEDGER_SQL, (window_h,)) or []:
        if status not in ('failed', 'partial'):
            continue
        problems.append({
            'artist_id': artist_id,
            'artist_name': name,
            'platform': platform,
            'dag_id': dag_id,
            'status': status,
            # The literal cause, already redacted at write time by safe_error.
            'reason': (error_message or 'no cause recorded')[:300],
            'when': str(started_at),
            # Nights failed since the last success — 1 means "broke tonight".
            'failing_nights': int(failing_nights or 1),
            'last_success': str(last_success) if last_success else None,
        })
    # Le plus RÉCENT en premier : ce qui vient de casser est ce sur quoi une
    # exécution peut encore agir.
    problems.sort(key=failure_age_nights)
    return problems
