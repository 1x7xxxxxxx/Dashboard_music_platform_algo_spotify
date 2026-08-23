"""Volume pillar: is a tenant's collection arriving SHORT?

Type: Utility
Uses: nothing (stdlib only — must be importable without Airflow)
Triggers: alert_monitor.check_row_dips
Depends on: —
Persists in: nothing

Why this is a module and not four lines inside the DAG: no DAG in this repo can be
imported outside a container. The installed Airflow rejects `schedule_interval`, so any
test that reaches for `alert_monitor` gets a `TypeError` and — if it guards the import —
**skips in silence**. That is the failure mode `tests/conftest.py` already documents for
the database gate: a run that proves nothing while reading green. The decision therefore
lives here, where a test can reach it with no Airflow at all.

The rule it encodes (R39, from Moses/Gavish/Vorwerck, *Data Quality Fundamentals* p.144
— **Volume: "Has all the data arrived?"**): a collection that arrives but arrives short
is invisible to every other check we run. Freshness sees rows and is happy; the spike
detector looks the other way and is happy. The hole between them is where SoundCloud
reported "✅ on 0 titles" and Benken's YouTube channel came back empty.
"""
from __future__ import annotations

# Mesuré sur la prod du 2026-08-23, pas choisi : les volumes réels par locataire y sont
# 1498/j (canari 14), 19/j (admin 1) et 7/j (Benken 12). Le premier plancher écrit ici
# valait 30 — il aurait rendu le détecteur aveugle à DEUX locataires sur trois, dont
# précisément celui qui a une panne de collecte vivante. Un seuil rond n'est pas une
# calibration.
MIN_BASELINE_ROWS = 5.0

# Un tiers du volume habituel. Au-dessus, on entre dans la variation normale d'un
# catalogue qui bouge ; en dessous, il manque la majorité des lignes.
DIP_RATIO = 3.0


def is_partial_collection(recent: float | None, baseline: float | None) -> bool:
    """`True` si `recent` est une collecte réelle mais très en dessous de `baseline`.

    Zéro n'appartient PAS à ce prédicat : la fraîcheur couvre déjà la source muette, et
    le signaler ici doublerait chaque alerte de source morte. Une référence absente
    (locataire trop récent) n'est pas non plus un constat — on ne compare à rien.
    """
    if recent is None or baseline is None:
        return False
    if recent <= 0:
        return False
    if baseline < MIN_BASELINE_ROWS:
        return False
    return recent < baseline / DIP_RATIO


def dip_finding(table: str, tenant: int, recent: float, baseline: float,
                day: str) -> dict:
    """Le constat, dans la forme que l'e-mail consolidé sait rendre."""
    return {
        "table": table,
        "tenant": int(tenant),
        "recent": int(recent),
        "baseline": round(float(baseline), 1),
        "day": day,
    }
