"""Les écoutes QUOTIDIENNES par plateforme — chaque grandeur ramenée à la même.

Type: Utility
Uses: PostgresHandler (passé, jamais ouvert ici)
Depends on: s4a_song_timeline, youtube_channel_history, soundcloud_tracks_daily
Persists in: nothing

Pourquoi ce module existe
-------------------------
Toutes nos sources ne mesurent pas la même chose, et les additionner sans le savoir
produit un graphique faux qui a l'air d'un graphique. C'est le défaut signalé le
2026-09-08 — « les datas sont incohérentes » — et il était mesurable :

    SELECT date, streams          FROM s4a_song_timeline       -- QUOTIDIEN
     WHERE song NOT ILIKE '%1x7xxxxxxx%'
    UNION ALL
    SELECT collected_at::date, playback_count
                                   FROM soundcloud_tracks_daily -- CUMUL DEPUIS TOUJOURS

(Le filtre de la ligne « Total » est recopié ici à dessein : `test_the_total_row_is_
always_filtered_out` lit TOUTES les chaînes du fichier, docstring comprise, et une
illustration sans filtre le ferait rougir sur sa propre documentation — la classe
`a-textual-guard-matches-its-own-documentation`. Ce que cet exemple montre de faux
est l'UNION d'un quotidien et d'un cumul, pas le filtre.)

`playback_count` est le total d'écoutes d'un titre depuis sa publication. Sommé par
jour, il rendait **23 560 « écoutes » le 8 septembre** pour l'artiste 1, tous les jours,
à côté d'un maximum réel de 1 605 streams/jour côté Spotify. La courbe montrait donc de
vrais chiffres quotidiens jusqu'au 2025-12-16, puis une falaise vers un plateau plat qui
n'est pas une écoute mais une accumulation.

Ce que chaque source mesure, et ce qu'on en fait
-----------------------------------------------
=============== ============================== ============ =======================
plateforme      table / colonne                nature       conversion
=============== ============================== ============ =======================
Spotify (S4A)   s4a_song_timeline.streams      quotidien    somme (MAX par jour+titre)
YouTube         youtube_channel_history        cumul        écart d'un jour à l'autre
                .view_count
SoundCloud      soundcloud_tracks_daily        cumul        écart par titre, puis somme
                .playback_count
Apple Music     apple_songs_performance.plays  cumul, UN    **exclu** — voir plus bas
                                               instantané
=============== ============================== ============ =======================

**Apple Music est exclu, et c'est dit plutôt que caché.** Sa table ne porte qu'un
instantané par dépôt de CSV (11 lignes, toutes du même jour, pour l'artiste 1) : il n'y
a aucune série à tracer. Le mettre à zéro dessinerait une plateforme muette là où il n'y
a pas de mesure — `MISSING_HISTORY` le nomme pour que l'appelant l'écrive.

Deux règles, et chacune vient d'un artefact MESURÉ le 2026-09-08
----------------------------------------------------------------
L'écart est calculé PAR POSTGRES, jamais en Python — même règle que
`freshness_monitor` : une seule horloge, une seule source de vérité pour l'ordre des
jours. Mais un `LAG` nu ne suffisait pas, et le prouver a demandé de regarder les
chiffres plutôt que d'y réfléchir.

**1. L'écart se prend sur le MAXIMUM déjà vu, pas sur la veille.** Le 2026-06-01, la
collecte SoundCloud de l'artiste 1 a écrit **0 pour ses 19 titres** — une collecte
ratée, pas une disparition d'écoutes. `GREATEST(x - LAG(x), 0)` absorbait bien la
fausse chute, puis attribuait toute la remontée au jour suivant : **23 480 écoutes le
2026-06-05**, sur un artiste qui en fait une vingtaine par jour. Une remontée qui ne
fait que retrouver un maximum déjà atteint n'est pas de l'activité.

**2. Un écart ne vaut qu'entre deux jours CONSÉCUTIFS.** Entre le 2025-12-16 et le
2026-03-30, le compteur a gagné 163 écoutes en 104 jours ; les poser sur le 30 mars
dessinerait un pic qui n'a pas eu lieu, et les étaler serait une invention. Le jour
n'a donc **aucun point** — un trou dans la courbe, qui est la forme honnête de « on ne
sait pas », alors qu'un zéro affirmerait « aucune écoute ».

Le premier jour observé n'a pas d'écart non plus (rien avant lui) : inventer un premier
point égal au cumul est exactement le défaut qu'on corrige ici.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Le filtre de la ligne « Total » des CSV S4A (règle transverse du dépôt). Écrit DANS
# la requête et non passé en paramètre : `tests/test_the_total_row_is_always_filtered_out`
# lit le texte du SQL, et un `%s` lui cache le filtre — un garde qui ne peut pas voir
# le filtre doit refuser la requête, ce qu'il a fait.

# Ordre d'affichage et libellés — les mêmes mots que les tuiles de l'accueil.
PLATFORM_LABELS = {
    "spotify": "🎵 Spotify",
    "youtube": "🎬 YouTube",
    "soundcloud": "☁️ SoundCloud",
}

# Les couleurs de marque, pour que la courbe et la tuile parlent de la même chose.
PLATFORM_COLORS = {
    "spotify": "#1DB954",
    "youtube": "#FF0000",
    "soundcloud": "#FF5500",
}

# Ce dont on ne PEUT pas tracer l'évolution, et pourquoi. L'appelant l'affiche ; il ne
# le devine pas, et il ne dessine surtout pas une ligne à zéro à la place.
MISSING_HISTORY = {
    "apple": ("🍎 Apple Music",
              "un seul relevé par dépôt de CSV — pas d'historique à tracer"),
}

# Le minimum pour qu'une courbe dise quelque chose — le même esprit que `MIN_POINTS`
# de `welcome_figures`, mais compté sur ce qui est RÉELLEMENT traçable après
# conversion des cumuls, pas sur le nombre de lignes en base.
MIN_POINTS_DRAWN = 7

_SQL_SPOTIFY = """
    SELECT date AS jour, SUM(daily_max)::bigint AS ecoutes FROM (
        SELECT date, song, MAX(streams) AS daily_max
          FROM s4a_song_timeline
         WHERE artist_id = %s AND song NOT ILIKE '%%1x7xxxxxxx%%' AND date IS NOT NULL
         GROUP BY date, song
    ) t GROUP BY date ORDER BY date
"""

# Compteur de CHAÎNE — et un locataire peut en avoir PLUSIEURS. La première version
# prenait `MAX(view_count)` par jour, toutes chaînes confondues : sur le bac à sable,
# qui porte trois `channel_id` (deux chaînes réelles plus une d'un onboarding
# abandonné, à 155 vues), elle sautait de 155 à 120 627 d'un jour à l'autre et
# affichait **120 472 vues en une journée**. Ce n'était pas une journée, c'était un
# changement de chaîne. On partitionne donc par chaîne, comme SoundCloud par titre.
_SQL_YOUTUBE = """
    SELECT jour, SUM(GREATEST(view_count - vu_max, 0))::bigint FROM (
        SELECT jour, channel_id, view_count,
               MAX(view_count) OVER (PARTITION BY channel_id ORDER BY jour
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS vu_max,
               LAG(jour) OVER (PARTITION BY channel_id ORDER BY jour) AS veille
          FROM (
            SELECT collected_at::date AS jour, channel_id, MAX(view_count) AS view_count
              FROM youtube_channel_history
             WHERE artist_id = %s AND view_count IS NOT NULL
             GROUP BY 1, 2
          ) t
    ) w WHERE vu_max IS NOT NULL AND jour - veille = 1 GROUP BY jour ORDER BY jour
"""

# Compteur PAR TITRE : l'écart se prend titre par titre AVANT d'additionner. Le prendre
# sur la somme ferait apparaître le cumul entier d'un titre le jour de sa première
# collecte — un pic qui n'est pas une écoute.
_SQL_SOUNDCLOUD = """
    SELECT jour, SUM(GREATEST(playback_count - vu_max, 0))::bigint FROM (
        SELECT jour, track_id, playback_count,
               MAX(playback_count) OVER (PARTITION BY track_id ORDER BY jour
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS vu_max,
               LAG(jour) OVER (PARTITION BY track_id ORDER BY jour) AS veille
          FROM (
            SELECT collected_at::date AS jour, track_id, MAX(playback_count) AS playback_count
              FROM soundcloud_tracks_daily
             WHERE artist_id = %s AND playback_count IS NOT NULL
             GROUP BY 1, 2
          ) d
    ) s WHERE vu_max IS NOT NULL AND jour - veille = 1 GROUP BY jour ORDER BY jour
"""


def _rows(db: Any, sql: str, params: tuple) -> list[tuple]:
    """Ne lève jamais : ces courbes sont un affichage, pas un calcul de facturation."""
    try:
        return [(r[0], int(r[1] or 0)) for r in (db.fetch_query(sql, params) or [])
                if r[0] is not None and r[1] is not None]
    except Exception as exc:      # noqa: BLE001 — une page qui plante coûte plus qu'une courbe absente
        logger.warning("platform series unavailable: %s", type(exc).__name__)
        return []


def daily_streams_by_platform(db: Any, artist_id: Optional[int]) -> dict:
    """{plateforme: [(jour, écoutes du jour), …]} — vide pour ce qui n'a pas de série.

    Chaque valeur est une quantité du JOUR, jamais un cumul : c'est la seule condition
    pour que deux plateformes puissent figurer sur le même axe.
    """
    if db is None or artist_id is None:
        return {}
    return {
        "spotify": _rows(db, _SQL_SPOTIFY, (artist_id,)),
        "youtube": _rows(db, _SQL_YOUTUBE, (artist_id,)),
        "soundcloud": _rows(db, _SQL_SOUNDCLOUD, (artist_id,)),
    }


def combined_daily_streams(series: dict) -> list[tuple]:
    """La somme jour par jour des plateformes qui savent la donner.

    Un jour n'est présent que si AU MOINS une plateforme l'a mesuré ; les absentes n'y
    comptent pas pour zéro. Additionner un zéro d'absence à une mesure ferait baisser
    un total le jour où une source n'a pas tourné, ce qui se lit comme une chute.
    """
    total: dict = {}
    for rows in (series or {}).values():
        for day, value in rows:
            total[day] = total.get(day, 0) + value
    return sorted(total.items())


def measured_days(series: dict, key: str, since=None, until=None) -> int:
    """Combien de jours cette plateforme a-t-elle été MESURÉE sur la période.

    Zéro mesure et zéro écoute ne sont pas la même chose, et l'écran les affichait
    pareil. Signalé le 2026-09-08 : « on a des 0 sur youtube et soundcloud, je pense
    qu'on a tout simplement pas la data ». Un appelant qui obtient 0 ici doit écrire
    « — », jamais « 0 ».
    """
    return sum(1 for d, _ in (series or {}).get(key, [])
               if (since is None or d >= since) and (until is None or d <= until))


def followers_change(db, artist_id, since=None, until=None):
    """(premier, dernier, écart) des abonnés Instagram sur la période, ou `None`.

    `instagram_daily_stats.followers_count` est un ÉTAT, pas un flux : on ne l'additionne
    pas, on compare ses deux extrémités. C'est pour ça que cette fonction ne vit pas dans
    `daily_streams_by_platform`, qui ne rend que des quantités du jour.

    Rend `None` s'il n'y a pas DEUX relevés dans la période : un écart a besoin de deux
    points, et afficher « +0 » sur un seul relevé serait une affirmation qu'on n'a pas
    mesurée.
    """
    if db is None or artist_id is None:
        return None
    sql = ("SELECT collected_at::date AS jour, MAX(followers_count) "
           "FROM instagram_daily_stats "
           "WHERE artist_id = %s AND followers_count IS NOT NULL")
    params: list = [artist_id]
    if since is not None:
        sql += " AND collected_at::date >= %s"
        params.append(since)
    if until is not None:
        sql += " AND collected_at::date <= %s"
        params.append(until)
    sql += " GROUP BY 1 ORDER BY 1"
    try:
        rows = [(r[0], int(r[1])) for r in (db.fetch_query(sql, tuple(params)) or [])
                if r[1] is not None]
    except Exception as exc:      # noqa: BLE001 — un compteur décoratif ne casse pas la page
        logger.warning("followers change unavailable: %s", type(exc).__name__)
        return None
    if len(rows) < 2:
        return None
    return rows[0][1], rows[-1][1], rows[-1][1] - rows[0][1]
