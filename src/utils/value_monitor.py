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


# ── Les cibles et la requête, sorties du DAG le 2026-09-12 ────────────────────
#
# Le docstring de ce module annonçait déjà « le prédicat vit ici, testable sans
# Airflow » alors que le SQL — la partie difficile, celle qui porte la fenêtre et la
# comparaison au maximum ANTÉRIEUR — était resté de l'autre côté. Un module qui
# promet d'être testable et laisse sa moitié la plus subtile dans un DAG ne tient pas
# sa promesse : ce dépôt a mesuré qu'un DAG n'est pas importable hors conteneur, donc
# ce SQL n'était exerçable par personne.
#
ZERO_RESET_TARGETS = [
    ("soundcloud_tracks_daily", "playback_count", "track_id", "collected_at"),
    ("youtube_video_stats", "view_count", "video_id", "collected_at"),
]
_ZR_TABLES = frozenset(t for t, _c, _e, _d in ZERO_RESET_TARGETS)
_ZR_COLUMNS = frozenset(
    [c for _t, c, _e, _d in ZERO_RESET_TARGETS]
    + [e for _t, _c, e, _d in ZERO_RESET_TARGETS]
    + [d for _t, _c, _e, d in ZERO_RESET_TARGETS]
)


def run(db, logger) -> list[dict]:
    """Les collectes qui ont écrit des zéros sur des compteurs cumulés.

    `logger` est injecté plutôt qu'importé : ce module ne dépend de rien, et c'est
    ce qui le rend appelable depuis un test, un DAG et un script.
    """
    resets = []
    try:
        for table, col, entity, date_col in ZERO_RESET_TARGETS:
            # Règle #8 : allowlist AVANT l'interpolation, jamais après.
            if (table not in _ZR_TABLES or col not in _ZR_COLUMNS
                    or entity not in _ZR_COLUMNS or date_col not in _ZR_COLUMNS):
                logger.warning(f"Zero-reset: identifiant hors allowlist: {table}.{col}")
                continue
            # Le maximum ANTÉRIEUR de la même entité, jamais la veille seule : une
            # collecte peut sauter des jours, et comparer au dernier point connu ferait
            # dépendre le verdict de la régularité de la collecte plutôt que de la
            # valeur. C'est la même règle que la conversion cumul → quotidien.
            rows = db.fetch_query(
                f"""WITH d AS (
                        SELECT artist_id, {entity} AS entity,
                               {date_col}::date AS day, max({col}) AS v
                        FROM {table}
                        WHERE artist_id IS NOT NULL
                        GROUP BY 1, 2, 3
                    ),
                    flagged AS (
                        SELECT artist_id, day, entity,
                               max(v) OVER (PARTITION BY artist_id, entity
                                            ORDER BY day
                                            ROWS BETWEEN UNBOUNDED PRECEDING
                                                     AND 1 PRECEDING) AS prev_max,
                               v
                        FROM d
                    )
                    SELECT artist_id, day::text,
                           count(*) FILTER (WHERE prev_max > 0 AND v = 0),
                           count(*)
                    FROM flagged
                    -- SUR LE DERNIER JOUR COMPLET, comme `check_row_dips`, et pour la
                    -- même raison. Sans cette borne le détecteur balaie tout
                    -- l'historique : lancé en production le 2026-09-08, il a remonté
                    -- l'incident du **2026-06-01** — juste, et qu'il aurait alors
                    -- répété chaque nuit pendant trois mois. Un détecteur qui redit
                    -- tous les jours un fait vieux de trois mois est la classe
                    -- `watchdog-becomes-the-noise`, déjà au catalogue.
                    --
                    -- Le jour EN COURS est exclu : une collecte à moitié écrite
                    -- ressemble à une collecte fautive, et l'alerte partirait chaque
                    -- matin. Deux détecteurs voisins avec deux politiques de fenêtre
                    -- seraient illisibles ; celle-ci est celle du pilier Volume.
                    WHERE day = (SELECT max(day) FROM d WHERE day < CURRENT_DATE)
                    GROUP BY 1, 2
                    HAVING count(*) FILTER (WHERE prev_max > 0 AND v = 0) > 0
                    ORDER BY 1"""
            )
            for tenant, day, hit, total in rows or []:
                if is_reportable(hit, total):
                    resets.append(zero_reset_finding(table, col, tenant, day,
                                                     hit, total))
                    logger.warning(
                        f"Zero reset: {table}.{col} tenant={tenant} {hit}/{total} "
                        f"counters back to zero on {day}"
                    )
    finally:
        db.close()

    return resets
