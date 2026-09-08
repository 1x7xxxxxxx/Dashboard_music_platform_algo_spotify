"""Pilier « valeurs » : les lignes sont arrivées, mais que VALENT-elles ?

Type: Utility
Uses: nothing (stdlib only — must be importable without Airflow)
Triggers: alert_monitor.check_zero_resets
Depends on: —
Persists in: nothing

Le trou que ce module ferme, mesuré le 2026-09-08 sur `soundcloud_tracks_daily` :

    2026-06-01 · artiste 1 · 19 titres · 19 à zéro (100 %)
    tous les autres jours   · 19 titres ·  0 à zéro (0 %)

Une collecte a écrit **19 compteurs cumulés à 0** pour des titres qui en portaient
plusieurs milliers la veille. Aucun contrôle ne l'a vu, et chacun avait raison de ne pas
le voir : la fraîcheur voit des lignes du jour ; `check_row_anomalies` regarde les pics ;
`is_partial_collection` (pilier Volume, R39) exclut explicitement zéro **en nombre de
lignes** — ici il y avait dix-neuf lignes, toutes fausses. La figure les absorbe déjà en
refusant les deltas négatifs ; tous les autres lecteurs de la table, eux, croient au
zéro.

POURQUOI PAS LE TAUX DE ZÉROS, qui est le patron du livre
---------------------------------------------------------
Moses/Gavish/Vorwerck, *Data Quality Fundamentals* p. 117, décrivent le suivi du taux de
valeurs nulles ou vides d'un jour comparé au précédent. Appliqué tel quel ici, il est
inutilisable, et c'est mesuré, pas supposé — « taux de zéros du jour > 2× celui de la
veille », rejoué sur l'historique réel de l'artiste 1 :

    s4a_song_timeline       1 254 jours → **93 alertes**
    soundcloud_tracks_daily    19 jours →   1 alerte  (le 2026-06-01)
    youtube_video_stats        34 jours →   0 alerte

Les 93 sont du bruit, et pour une raison de FORME : `s4a_song_timeline.streams` est une
quantité du jour, où zéro veut dire « ce titre n'a pas été écouté aujourd'hui » — c'est
27 à 55 % du catalogue chaque jour, tous les jours. Un détecteur qui crie 93 fois est un
détecteur que personne ne lit.

Le prédicat ci-dessous ne s'applique donc qu'aux **compteurs cumulés**, où un retour à
zéro est arithmétiquement impossible : un compteur de lectures ne redescend pas. Sur les
mêmes données il sonne **une fois**, sur le seul incident réel.

C'est le même invariant que tout le reste de cette séance : on ne traite pas de la même
façon une quantité du jour et un cumul. Un détecteur non plus.
"""
from __future__ import annotations

# En dessous, un « retour à zéro » n'est pas un signal : un locataire qui a deux titres
# et en supprime un ne mérite pas une alerte. Mesuré : l'incident du 2026-06-01 portait
# sur 19 entités d'un coup, et les volumes réels par locataire sont 19 (admin 1),
# 1 498 (canari 14) et 7 (Benken 12) lignes/jour — un plancher de 3 les couvre tous.
MIN_ENTITIES = 3


def is_zero_reset(previous_max, current) -> bool:
    """`True` si un compteur CUMULÉ est revenu à zéro — arithmétiquement impossible.

    Ni « jamais vu » (`previous_max` absent : première collecte, rien à comparer), ni
    « toujours à zéro » (une vidéo publiée hier et jamais vue est légitimement à 0). Ce
    qui est faux, c'est de DESCENDRE à zéro.
    """
    if previous_max is None or current is None:
        return False
    return previous_max > 0 and current == 0


def zero_reset_finding(table: str, column: str, tenant: int, day: str,
                       entities: int, total: int) -> dict:
    """Le constat, dans la forme que l'e-mail consolidé sait rendre.

    `entities` sur `total` : dire « 19 titres sur 19 » et non « 19 titres » est ce qui
    permet de distinguer une collecte entièrement ratée d'un titre retiré du catalogue.
    """
    return {
        "table": table,
        "column": column,
        "tenant": int(tenant),
        "day": day,
        "entities": int(entities),
        "total": int(total),
    }


def is_reportable(entities: int, total: int) -> bool:
    """Assez d'entités touchées pour que ce soit une collecte, pas un cas isolé."""
    if not entities or entities < MIN_ENTITIES:
        return False
    return entities <= (total or entities)
