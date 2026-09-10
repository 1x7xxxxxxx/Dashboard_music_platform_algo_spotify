"""Distinguer une collecte qui vient de casser d'une collecte bloquée depuis des mois.

Type: Utility
Uses: nothing (pure)
Depends on: nothing
Triggers: airflow/dags/alert_monitor.py (check_collection_outcomes + le rendu de l'e-mail)
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
