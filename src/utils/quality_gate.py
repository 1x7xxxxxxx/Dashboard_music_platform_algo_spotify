"""Circuit breaker: never judge the SHAPE of data that is already dead.

Type: Utility
Uses: datetime (stdlib only — must be importable without Airflow)
Triggers: data_quality_check.check_spotify_data_consistency
Depends on: —
Persists in: nothing

R42. Moses/Gavish/Vorwerck (*Data Quality Fundamentals*, p.86) make the circuit breaker
depend on three things — lineage, profiling across the pipeline, and the ability to trip
the circuit automatically from what profiling finds. The part that applies here is the
ordering: **Freshness and Distribution are separate pillars** (p.144), and a distribution
check that does not stand on a freshness check is measuring the shape of a corpse.

streaMLytics found this the expensive way before reading it. `data_quality_check` has
never run once (`is_paused = t`, `last_start` empty), and its Meta task would have gone
GREEN on the most stale source in production: it read `MAX(collected_at)` — the write
time, which advances every night as the DAG rewrites the same old rows — while the data
itself (`MAX(day_date)`) stopped in 2024. That is the `freshness-measured-on-write-time`
class, and a second voice contradicting the correct one is worse than no voice at all.

So: no verdict on completeness, accuracy or consistency until the source is proven fresh.
Abstaining is a RESULT here, not a failure — it is reported, never raised.
"""
from __future__ import annotations

from datetime import date, timedelta

# Une timeline S4A alimentée quotidiennement. Au-delà, ce n'est plus « en retard »,
# c'est « la source ne livre plus » — et ça, c'est le travail de `freshness_monitor`,
# déjà branché sur l'e-mail nocturne. Deux voix sur le même fait se contredisent tôt
# ou tard ; celle-ci se tait.
MAX_SOURCE_AGE_DAYS = 3


def source_is_fresh_enough(last_data_day: date | None, today: date,
                           max_age_days: int = MAX_SOURCE_AGE_DAYS) -> bool:
    """`True` si la donnée elle-même est assez récente pour qu'on juge sa forme.

    `last_data_day` doit être la date PORTÉE PAR LA DONNÉE (`MAX(date)`), jamais sa date
    d'écriture (`MAX(collected_at)`) : un DAG qui réécrit chaque nuit les mêmes vieilles
    lignes fait avancer la seconde et pas la première. C'est précisément le piège dans
    lequel la tâche Meta de ce DAG serait tombée.
    """
    if last_data_day is None:
        return False
    return last_data_day >= today - timedelta(days=max_age_days)


def abstention_note(last_data_day: date | None, today: date) -> str:
    """Le constat rendu quand le circuit s'ouvre — il doit nommer le pourquoi."""
    if last_data_day is None:
        return ("aucune donnée S4A : contrôles de qualité non exécutés (rien à juger). "
                "La source muette est le sujet de freshness_monitor, pas d'ici.")
    age = (today - last_data_day).days
    return (f"donnée S4A périmée de {age} j (dernier jour porté : {last_data_day}) : "
            f"contrôles de qualité non exécutés. Juger la forme d'une donnée morte "
            f"produirait des constats vrais sur le passé et faux sur le présent.")
