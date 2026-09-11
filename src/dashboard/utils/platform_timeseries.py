"""Les écoutes QUOTIDIENNES par plateforme — chaque grandeur ramenée à la même.

Type: Utility
Uses: PostgresHandler (passé, jamais ouvert ici)
Depends on: s4a_song_timeline, youtube_video_stats, soundcloud_tracks_daily
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
YouTube         youtube_video_stats.view_count cumul        écart par vidéo, puis somme
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

import datetime as _dt
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
    # Apple n'a de valeurs qu'au pas ANNUEL — ses exports sont des totaux de période.
    # Elle est donc dans les libellés, mais sa série n'existe qu'à ce pas-là
    # (`apple_yearly_series`), et l'accueil ne la propose que là.
    "apple": "🎎 Apple Music",
}

# Les plateformes qui n'ont de série qu'à un pas donné. Lu par l'accueil pour ne pas
# proposer une source qui ne pourrait rien tracer.
STEP_ONLY = {"apple": "year"}

# Ce dont on ne PEUT pas tracer l'évolution, et pourquoi. L'appelant l'affiche ; il ne
# le devine pas, et il ne dessine surtout pas une ligne à zéro à la place.
MISSING_HISTORY = {}

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

# Compteur PAR VIDÉO — et non le compteur de la CHAÎNE, qui donnait des chiffres faux.
#
# Mesuré le 2026-09-08 contre YouTube Studio, qui annonçait **64 vues** sur la période :
#
#   youtube_channel_history.view_count : 120 627 pendant onze jours, puis 120 987
#                                        → +360 attribués à une seule journée
#   somme des youtube_video_stats      : +3, 0, +3, 0, +1, +1, +3… soit 44 sur 28 jours
#
# Le compteur de chaîne est mis à jour par PALIERS et porte autre chose que la somme des
# vidéos (vidéos privées ou supprimées, agrégats internes). La somme par vidéo suit le
# même ordre de grandeur que Studio ; l'écart qui reste (44 contre 64) tient à la
# granularité du relevé quotidien et aux vidéos qui ont quitté la chaîne, pas à un
# facteur dix.
#
# L'écart se prend PAR VIDÉO avant d'additionner, pour la même raison que SoundCloud le
# prend par titre : le prendre sur la somme ferait apparaître le cumul entier d'une
# vidéo le jour de sa première collecte.
_SQL_YOUTUBE = """
    SELECT jour, SUM(GREATEST(view_count - vu_max, 0))::bigint FROM (
        SELECT jour, video_id, view_count,
               MAX(view_count) OVER (PARTITION BY video_id ORDER BY jour
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS vu_max,
               LAG(jour) OVER (PARTITION BY video_id ORDER BY jour) AS veille
          FROM (
            SELECT collected_at::date AS jour, video_id, MAX(view_count) AS view_count
              FROM youtube_video_stats
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


# ── CE QUE LA CONVERSION CUMUL → QUOTIDIEN JETTE ────────────────────────────
#
# Un écart n'est calculé qu'entre deux jours CONSÉCUTIFS (`jour - veille = 1`). C'est
# la seule règle honnête : entre deux relevés distants de neuf jours, on sait ce qui
# s'est passé EN TOUT, jamais quel jour. L'attribuer au dernier jour inventerait un pic.
#
# Mais jeter en silence est un autre défaut. YouTube n'est mesurée que 39 % des jours :
# la majorité des écoutes réelles n'entre donc ni dans la courbe, ni dans les totaux de
# période, et rien ne le disait. Ces requêtes comptent ce qui a été écarté, pour qu'on
# puisse le NOMMER — ce qui manque n'est pas la donnée, c'est l'aveu.
_SQL_DISCARDED_YOUTUBE = """
    SELECT COUNT(*)::int AS trous,
           COALESCE(SUM(jour - veille - 1), 0)::int AS jours_non_couverts,
           COALESCE(SUM(GREATEST(view_count - vu_max, 0)), 0)::bigint AS ecoutes_ecartees
      FROM (
        SELECT jour, view_count,
               MAX(view_count) OVER (PARTITION BY video_id ORDER BY jour
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS vu_max,
               LAG(jour) OVER (PARTITION BY video_id ORDER BY jour) AS veille
          FROM (
            SELECT collected_at::date AS jour, video_id, MAX(view_count) AS view_count
              FROM youtube_video_stats
             WHERE artist_id = %s AND view_count IS NOT NULL
             GROUP BY 1, 2
          ) t
    ) w WHERE vu_max IS NOT NULL AND jour - veille > 1
"""

_SQL_DISCARDED_SOUNDCLOUD = _SQL_DISCARDED_YOUTUBE.replace(
    "view_count", "playback_count").replace("video_id", "track_id").replace(
    "youtube_video_stats", "soundcloud_tracks_daily")


# ── LA SÉRIE QUI ABOUTIT AU TOTAL OR ───────────────────────────────────────
#
# `v_platform_totals` (migration 097) définit le total YouTube : le DERNIER compteur
# connu de CHAQUE vidéo, additionné. La couche or définissait donc un scalaire sans
# définir la courbe qui y mène — et une courbe dont le dernier point contredit la
# tuile est exactement la contradiction qu'ADR-019 existe pour empêcher.
#
# Le report en avant (`carried`) est ce qui rend l'égalité VRAIE PAR CONSTRUCTION :
# une vidéo non relevée un jour garde sa dernière valeur connue au lieu de disparaître
# de la somme. Sans lui la courbe plonge les jours de collecte partielle — YouTube
# n'est mesurée que 39 % des jours — et son dernier point ne vaut le total que par
# chance, le jour où toutes les vidéos ont été relevées.
#
# `COUNT(...) OVER (…)` compte les relevés non nuls vus jusqu'ici : il est constant
# entre deux relevés, donc chaque groupe contient exactement UNE valeur, que le `MAX`
# diffuse. C'est un report de la dernière valeur, pas un maximum courant — la
# distinction compte le jour où un compteur recule (vidéo passée en privé), car c'est
# le recul que la couche or retient.
_SQL_YT_CUMULATIVE = """
    WITH per_day AS (
        SELECT video_id, collected_at::date AS j, MAX(view_count) AS vc
          FROM youtube_video_stats
         WHERE artist_id = %s AND view_count IS NOT NULL
         GROUP BY 1, 2
    ), grid AS (
        SELECT v.video_id, d.j
          FROM (SELECT DISTINCT video_id FROM per_day) v
          CROSS JOIN (SELECT DISTINCT j FROM per_day) d
    ), filled AS (
        SELECT g.video_id, g.j, p.vc,
               COUNT(p.vc) OVER (PARTITION BY g.video_id ORDER BY g.j) AS grp
          FROM grid g
          LEFT JOIN per_day p ON p.video_id = g.video_id AND p.j = g.j
    ), carried AS (
        SELECT video_id, j, MAX(vc) OVER (PARTITION BY video_id, grp) AS vc FROM filled
    )
    SELECT j, SUM(vc)::bigint FROM carried WHERE vc IS NOT NULL GROUP BY j ORDER BY j
"""


def youtube_cumulative_views(db: Any, artist_id: Optional[int]) -> list[tuple]:
    """[(jour, vues cumulées)] — la somme des compteurs PAR VIDÉO, jamais celui de la chaîne.

    Le compteur de CHAÎNE (`youtube_channel_history.view_count`) porte des vidéos qui
    ne sont pas dans le catalogue lu ici — privées, supprimées, agrégats internes — et
    il avance par paliers : +360 vues attribuées à une seule journée le 2026-09-08
    quand YouTube Studio en annonçait 64 sur la période.

    L'export PDF l'a abandonné ce jour-là. **La page YouTube du dashboard, non.** Écart
    mesuré en production le 2026-09-11 pour l'artiste 1 : **120 627** sur cette page
    contre **118 219** dans la couche or. Deux nombres pour la même chose, dans le même
    produit — et le compteur de chaîne reste affiché ailleurs sur cette page, LABELLÉ
    « chaîne », ce qui est légitime : ce qui ne l'est pas, c'est de le tracer comme la
    série des vues des vidéos.

    Le dernier point de cette série égale `v_platform_totals` par construction.
    Garde : `tests/test_a_curve_ends_where_its_tile_says.py`.
    """
    if db is None or artist_id is None:
        return []
    return _rows(db, _SQL_YT_CUMULATIVE, (artist_id,))


# SoundCloud, même forme, même raison : `v_platform_totals` additionne le dernier
# `playback_count` connu de chaque titre. Écart mesuré pour l'artiste 1 le 2026-09-11 :
# la somme courante des deltas quotidiens rend **77**, le produit en compte **23 563**.
_SQL_SC_CUMULATIVE = _SQL_YT_CUMULATIVE.replace(
    "video_id", "track_id").replace(
    "view_count", "playback_count").replace(
    "youtube_video_stats", "soundcloud_tracks_daily")


def soundcloud_cumulative_plays(db: Any, artist_id: Optional[int]) -> list[tuple]:
    """[(jour, écoutes cumulées)] — dernier compteur connu par TITRE, additionné."""
    if db is None or artist_id is None:
        return []
    return _rows(db, _SQL_SC_CUMULATIVE, (artist_id,))


# UNE SEULE REQUÊTE POUR LES DEUX PLATEFORMES, sur la forme de `v_platform_totals`.
#
# Elles en faisaient deux, et le cliquet d'allers-retours de l'accueil l'a refusé :
# 14 contre un plafond de 13 gelé le 2026-09-10. Son message dit quoi faire — « elle
# la lit dans une requête existante ou passe par la couche or » — et c'est le même
# geste que la migration 097 a fait pour les totaux scalaires : un `UNION ALL` avec
# une colonne `platform`, une définition par plateforme, une seule lecture.
# UNE SEULE REQUÊTE POUR LES DEUX PLATEFORMES, sur la forme de `v_platform_totals`.
#
# Elles en faisaient deux, et le cliquet d'allers-retours de l'accueil l'a refusé :
# 14 contre un plafond de 13 gelé le 2026-09-10. Son message dit quoi faire — « elle
# la lit dans une requête existante ou passe par la couche or » — et c'est le même
# geste que la migration 097 a fait pour les totaux scalaires : un `UNION ALL` avec
# une colonne `platform`, une définition par plateforme, une seule lecture.
#
# Elle est ÉCRITE, pas fabriquée par substitution sur `_SQL_YT_CUMULATIVE` : la
# première version l'était, les CTE se sont mélangées et la requête rendait zéro
# ligne en silence — `_rows3` avale, donc les deux courbes disparaissaient sans un
# mot. Une requête assemblée par `.replace()` n'est lisible par personne, à commencer
# par celui qui la relit.
_SQL_CUMULATIVE_ALL = """
    WITH
    yt_day AS (
        SELECT video_id, collected_at::date AS j, MAX(view_count) AS vc
          FROM youtube_video_stats
         WHERE artist_id = %s AND view_count IS NOT NULL
         GROUP BY 1, 2
    ), yt_grid AS (
        SELECT e.video_id, d.j
          FROM (SELECT DISTINCT video_id FROM yt_day) e
          CROSS JOIN (SELECT DISTINCT j FROM yt_day) d
    ), yt_filled AS (
        SELECT g.video_id, g.j, p.vc,
               COUNT(p.vc) OVER (PARTITION BY g.video_id ORDER BY g.j) AS grp
          FROM yt_grid g
          LEFT JOIN yt_day p ON p.video_id = g.video_id AND p.j = g.j
    ), yt_carried AS (
        SELECT j, MAX(vc) OVER (PARTITION BY video_id, grp) AS vc FROM yt_filled
    ),
    sc_day AS (
        SELECT track_id, collected_at::date AS j, MAX(playback_count) AS vc
          FROM soundcloud_tracks_daily
         WHERE artist_id = %s AND playback_count IS NOT NULL
         GROUP BY 1, 2
    ), sc_grid AS (
        SELECT e.track_id, d.j
          FROM (SELECT DISTINCT track_id FROM sc_day) e
          CROSS JOIN (SELECT DISTINCT j FROM sc_day) d
    ), sc_filled AS (
        SELECT g.track_id, g.j, p.vc,
               COUNT(p.vc) OVER (PARTITION BY g.track_id ORDER BY g.j) AS grp
          FROM sc_grid g
          LEFT JOIN sc_day p ON p.track_id = g.track_id AND p.j = g.j
    ), sc_carried AS (
        SELECT j, MAX(vc) OVER (PARTITION BY track_id, grp) AS vc FROM sc_filled
    )
    SELECT 'youtube'::text AS platform, j, SUM(vc)::bigint
      FROM yt_carried WHERE vc IS NOT NULL GROUP BY j
    UNION ALL
    SELECT 'soundcloud'::text, j, SUM(vc)::bigint
      FROM sc_carried WHERE vc IS NOT NULL GROUP BY j
    ORDER BY 1, 2
"""


def cumulative_by_platform(db: Any, artist_id: Optional[int]) -> dict:
    """{plateforme: série CUMULÉE} — pour les seules plateformes à compteur.

    Spotify n'y figure pas, et c'est le fond du sujet : S4A livre des quantités
    QUOTIDIENNES et toutes les journées sont présentes, donc la somme courante de sa
    série est déjà son cumul exact. YouTube et SoundCloud livrent des COMPTEURS, dont
    la série quotidienne est une différence qui jette les journées non consécutives —
    cumuler ce qui reste donnait 21 au lieu de 118 219.

    Le dictionnaire dit donc littéralement : « voici les plateformes dont le cumul ne
    se déduit pas du quotidien ». `platform_chart` lit cette clé et retombe sur la
    somme courante pour les autres.

    Une seule requête, et une clé présente même vide : un appelant qui teste
    `if rows` doit pouvoir distinguer « cette plateforme a un compteur » de « cette
    plateforme n'en a pas », sans quoi une base sans SoundCloud la ferait traiter
    comme Spotify.
    """
    if db is None or artist_id is None:
        return {}
    out: dict = {"youtube": [], "soundcloud": []}
    for row in _rows3(db, _SQL_CUMULATIVE_ALL, (artist_id, artist_id)):
        platform, day, value = row
        if platform in out:
            out[platform].append((day, value))
    return out


def _rows3(db: Any, sql: str, params: tuple) -> list[tuple]:
    """Comme `_rows`, pour une requête qui rend (plateforme, jour, valeur)."""
    try:
        return [(r[0], r[1], int(r[2] or 0)) for r in (_q(db, sql, params) or [])
                if r[0] is not None and r[1] is not None]
    except Exception as exc:      # noqa: BLE001 — une courbe absente vaut mieux qu'une page morte
        logger.warning("cumulative series unavailable: %s", type(exc).__name__)
        return []


def discarded_deltas(db: Any, artist_id: Optional[int]) -> dict:
    """{plateforme: (trous, jours non couverts, écoutes écartées)} — ce qu'on ne trace pas.

    Rendu vide plutôt que faux si la lecture échoue : ce compte sert à AVOUER une
    imprécision, pas à en introduire une.
    """
    if db is None or artist_id is None:
        return {}
    out = {}
    for key, sql in (("youtube", _SQL_DISCARDED_YOUTUBE),
                     ("soundcloud", _SQL_DISCARDED_SOUNDCLOUD)):
        try:
            row = _q(db, sql, (artist_id,))
            if row and row[0][0]:
                out[key] = (int(row[0][0]), int(row[0][1] or 0), int(row[0][2] or 0))
        except Exception as exc:      # noqa: BLE001
            logger.warning("discarded deltas unreadable (%s): %s", key, type(exc).__name__)
    return out


# ── LE POINT OÙ UN CACHE PEUT SE BRANCHER, ET LE SEUL ───────────────────────
#
# Ce module reste SANS Streamlit : l'export PDF headless et les tests l'appellent.
# Un `@st.cache_data` sur ses fonctions publiques est donc impossible — et il
# serait faux même s'il était possible. Ces fonctions sont écrites pour NE JAMAIS
# LEVER : sur une panne de base elles rendent vide, indiscernable de « rien à
# lire ». Les envelopper dans un cache mettrait la PANNE en cache, et une
# coupure d'une seconde deviendrait « aucune donnée » pendant dix minutes, pour
# tous les spectateurs à la fois. C'est le constat CRITIQUE qui a fait refuser
# la première conception, le 2026-09-11.
#
# D'où ce crochet, placé À L'INTÉRIEUR de l'avalement : la couche Streamlit y
# installe une lecture mise en cache ; si elle lève, rien n'est mémorisé, le
# `except` ci-dessous dégrade comme avant, et le rendu suivant réessaie.
#
# La clé du cache est `(sql, params)`, et `params` porte toujours `artist_id` :
# l'isolation entre locataires est donc structurelle, pas une convention à
# respecter à chaque appel.
_FETCH = None


def set_fetch(fetch) -> None:
    """Installe la lecture du processus (`fetch(db, sql, params) -> rows`)."""
    global _FETCH
    _FETCH = fetch


def _q(db: Any, sql: str, params: tuple):
    """Lit, par le crochet du processus s'il y en a un."""
    if _FETCH is not None:
        return _FETCH(db, sql, params)
    return db.fetch_query(sql, params)


def _rows(db: Any, sql: str, params: tuple) -> list[tuple]:
    """Ne lève jamais : ces courbes sont un affichage, pas un calcul de facturation."""
    try:
        return [(r[0], int(r[1] or 0)) for r in (_q(db, sql, params) or [])
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
        rows = [(r[0], int(r[1])) for r in (_q(db, sql, tuple(params)) or [])
                if r[1] is not None]
    except Exception as exc:      # noqa: BLE001 — un compteur décoratif ne casse pas la page
        logger.warning("followers change unavailable: %s", type(exc).__name__)
        return None
    if len(rows) < 2:
        return None
    return rows[0][1], rows[-1][1], rows[-1][1] - rows[0][1]


# LA MÊME LECTURE, TROIS APPELANTS, UN SEUL ALLER-RETOUR.
#
# `_apple_readings` a trois appelants, et deux d'entre eux tirent au même rendu de
# l'accueil : mesuré le 2026-09-10, cette requête partait DEUX fois avec exactement
# les mêmes paramètres. Le mémo est attaché à la CONNEXION, pas à une horloge, pour
# une raison de durée de vie : une vue ouvre exactement une connexion par rendu via
# `view_session()`, refermée à la sortie. Le cache a donc précisément la durée d'un
# rendu — il ne peut ni se périmer trop tard, ni franchir la frontière d'un locataire.
#
# Un `st.cache_data` serait le réflexe, et il est refusé ici : ce module est
# volontairement sans Streamlit (l'export PDF headless et les tests l'appellent), et
# c'est la même règle qui a fait naître `lang_pref` à côté de `i18n`.
_APPLE_MEMO = "_apple_readings_memo"


def _apple_readings(db, artist_id):
    """[(début, fin, écoutes)] des relevés BORNÉS — `(None, None)` exclus."""
    memo = getattr(db, _APPLE_MEMO, None)
    if memo is None:
        memo = {}
        try:
            setattr(db, _APPLE_MEMO, memo)
        except AttributeError:
            # Une connexion qui refuse un attribut (doublure de test à `__slots__`)
            # relit simplement : le mémo est une optimisation, pas un contrat.
            memo = None
    if memo is not None and artist_id in memo:
        return memo[artist_id]
    try:
        rows = _q(db,
            "SELECT period_start, period_end, COALESCE(SUM(plays), 0)::bigint "
            "FROM apple_songs_performance "
            "WHERE artist_id = %s AND period_start IS NOT NULL "
            "  AND period_end IS NOT NULL "
            "GROUP BY 1, 2 ORDER BY 1, 2", (artist_id,))
    except Exception as exc:      # noqa: BLE001 — une tuile ne fait pas tomber la page
        logger.warning("apple readings unavailable: %s", type(exc).__name__)
        # Un échec n'est PAS mémorisé : le rendu suivant doit pouvoir réessayer, et
        # surtout une liste vide mise en cache se lirait « cet artiste n'a rien sur
        # Apple », ce qui est le mensonge que ce dépôt refuse partout ailleurs.
        return []
    out = [(r[0], r[1], int(r[2] or 0)) for r in (rows or [])]
    if memo is not None:
        memo[artist_id] = out
    return out


def non_overlapping_cover(readings: list) -> list:
    """Le sous-ensemble le plus FIN qui ne se chevauche pas — sinon on compte double.

    Depuis que la période se lit dans le nom du fichier, un artiste a naturellement des
    relevés IMBRIQUÉS : l'export « depuis le début » (2015-06-30 → 2026-09-04) et, à
    côté, celui de 2024. Les additionner compterait 2024 deux fois — une fois seul, une
    fois dans le cumul. C'est la même faute que celle qui a produit 23 560 « écoutes »
    par jour ce matin : additionner deux grandeurs qui se recouvrent.

    On garde donc les plus COURTS d'abord, et on n'ajoute un relevé que s'il ne
    chevauche aucun de ceux déjà retenus. Le résultat est le découpage le plus précis
    dont on dispose, sans jamais compter deux fois la même journée.
    """
    kept: list = []
    for start, end, plays in sorted(readings, key=lambda r: (r[1] - r[0], r[0])):
        if any(start <= k_end and k_start <= end for k_start, k_end, _ in kept):
            continue
        kept.append((start, end, plays))
    return sorted(kept)


def apple_period_plays(db, artist_id, since=None, until=None):
    """Les écoutes Apple sur la période, ou `None`. Deux chemins, dans cet ordre.

    Apple n'a pas de résolution quotidienne, mais depuis les migrations 093/094 chaque
    dépôt est un relevé qui SAIT ce qu'il couvre — et depuis le 2026-09-08 il le sait
    tout seul, en lisant les deux dates que Apple écrit dans le nom du fichier.

    * **des relevés bornés** : on somme le découpage non chevauchant qui tient dans la
      fenêtre. Ne jamais sommer à l'aveugle : ils s'imbriquent.
    * **des relevés « depuis le début » sans bornes connues** (déposés avant que la
      période soit lue) : ce sont des cumuls, donc on prend l'écart entre le premier et
      le dernier de la fenêtre.

    Mélanger les deux compterait deux fois les mêmes écoutes.
    """
    if db is None or artist_id is None:
        return None

    inside = [r for r in _apple_readings(db, artist_id)
              if (since is None or r[0] >= since) and (until is None or r[1] <= until)]
    cover = non_overlapping_cover(inside)
    if cover:
        return sum(plays for _s, _e, plays in cover)

    sql = ("SELECT snapshot_date, SUM(plays)::bigint FROM apple_songs_performance "
           "WHERE artist_id = %s AND plays IS NOT NULL AND period_start IS NULL")
    params: list = [artist_id]
    if since is not None:
        sql += " AND snapshot_date >= %s"
        params.append(since)
    if until is not None:
        sql += " AND snapshot_date <= %s"
        params.append(until)
    sql += " GROUP BY 1 ORDER BY 1"
    try:
        rows = [(r[0], int(r[1])) for r in (_q(db, sql, tuple(params)) or [])
                if r[1] is not None]
    except Exception as exc:      # noqa: BLE001
        logger.warning("apple period unavailable: %s", type(exc).__name__)
        return None
    if len(rows) < 2:
        return None
    return max(rows[-1][1] - rows[0][1], 0)


def apple_lifetime_plays(db, artist_id):
    """Le total Apple « depuis le début » — LU dans la couche or, jamais recalculé.

    La règle elle-même vit dans `gold_apple_lifetime()` (migration 102) et nulle part
    ailleurs. Elle choisit entre trois formes, par précision décroissante :

    1. le relevé borné le plus LARGE — l'export « depuis le début », qui contient déjà
       les années ;
    2. la somme du découpage non chevauchant — 2024 et 2025 additionnés, mais jamais
       2024 en plus d'un cumul qui le contient ;
    3. à défaut de tout relevé borné, le dernier instantané sans bornes.

    Cette fonction en portait une COPIE Python jusqu'au 2026-09-12. Les deux
    s'accordaient — vérifié sur tous les locataires — et c'est précisément ce qu'on ne
    peut pas garantir dans le temps : Apple était la dernière plateforme dont le total
    n'avait aucune définition SQL, et cinq fichiers lisaient sa table directement.
    C'est ainsi que YouTube a eu trois définitions avant la migration 097.

    Ne lève jamais : une tuile absente ne fait pas tomber une page.
    """
    if db is None or artist_id is None:
        return 0
    try:
        row = _q(db, "SELECT COALESCE(gold_apple_lifetime(%s), 0)::bigint",
                 (artist_id,))
        return int(row[0][0] or 0) if row else 0
    except Exception as exc:      # noqa: BLE001
        logger.warning("apple lifetime unavailable: %s", type(exc).__name__)
        return 0


def apple_lifetime_shazams(db, artist_id):
    """Les Shazams « depuis le début » — même règle que les plays, même fonction.

    `views/apple_music.py` en portait une copie Python, avec sa propre branche
    `if/else` : deux implémentations d'un même algorithme, dont une seule était
    testée. La métrique est désormais un PARAMÈTRE de `gold_apple_lifetime`
    (migration 103), validé contre une allowlist côté SQL.
    """
    if db is None or artist_id is None:
        return 0
    try:
        row = _q(db, "SELECT COALESCE(gold_apple_lifetime(%s, 'shazam_count'), 0)::bigint",
                 (artist_id,))
        return int(row[0][0] or 0) if row else 0
    except Exception as exc:      # noqa: BLE001
        logger.warning("apple shazams unavailable: %s", type(exc).__name__)
        return 0


def apple_snapshot_count(db, artist_id) -> int:
    """Combien de relevés Apple existent — pour DIRE pourquoi la tuile est vide.

    Un relevé = un couple (jour de dépôt, période couverte). Deux exports annuels
    déposés le même jour font bien deux relevés.
    """
    if db is None or artist_id is None:
        return 0
    try:
        row = _q(db,
            "SELECT COUNT(*) FROM (SELECT DISTINCT snapshot_date, period_start, "
            "period_end FROM apple_songs_performance WHERE artist_id = %s) r",
            (artist_id,))
        return int(row[0][0] or 0) if row else 0
    except Exception:      # noqa: BLE001
        return 0


def apple_yearly_series(db, artist_id) -> list:
    """[(1ᵉʳ janvier, écoutes)] — les relevés Apple qui tiennent dans UNE année civile.

    C'est la seule façon honnête de faire figurer Apple sur la même figure que les
    autres : ses exports sont des totaux de PÉRIODE, pas des quantités du jour. Étaler
    900 écoutes de 2024 sur 366 jours inventerait une valeur quotidienne que personne
    n'a mesurée — la faute que ce module existe pour empêcher.

    Au pas ANNUEL, en revanche, un export « 2024 » est exactement un point. Les relevés
    à cheval sur plusieurs années (l'export « depuis le début ») sont écartés : ils
    recouvriraient les années qu'ils contiennent.
    """
    readings = [r for r in _apple_readings(db, artist_id)
                if r[0].year == r[1].year]
    return [(_dt.date(start.year, 1, 1), plays)
            for start, _end, plays in non_overlapping_cover(readings)]


# ── UN SEUL CALCUL DE TOTAL ─────────────────────────────────────────────────
#
# Balayé le 2026-09-08 : il existait au moins QUATRE façons de calculer « le total »
# dans ce dépôt, et elles ne s'accordaient pas. L'accueil et l'export PDF additionnaient
# le compteur de CHAÎNE YouTube — celui qu'on a prouvé ~10× faux le matin même ; la page
# Apple sommait toutes ses lignes et comptait deux fois les années contenues dans un
# export « depuis le début » ; l'API rendait le cumul d'UNE SEULE vidéo comme total de la
# plateforme. Un même locataire lisait donc trois totaux différents sur trois pages.
#
# Ce module portait déjà les bonnes règles, une par forme. Il porte désormais leur
# APPLICATION, pour que les surfaces n'aient plus à choisir.

def platform_totals(db, artist_id, since=None, until=None) -> dict:
    """{plateforme: écoutes sur la période} — `None` quand rien n'a été mesuré.

    Deux régimes, et les confondre donnerait des chiffres faux :

    * **`since is None` — depuis le début.** Les compteurs que les plateformes annoncent
      aujourd'hui, qui portent tout ce qui précède notre première collecte. YouTube y est
      la somme des compteurs PAR VIDÉO (le dernier relevé de chacune) et non le compteur
      de chaîne : celui-ci avance par paliers et compte des vidéos qui ne sont pas les
      siennes.
    * **Une période bornée.** Spotify additionne ses quantités du jour : le CSV S4A les
      porte toutes, la somme est exacte. Pour un COMPTEUR — YouTube, SoundCloud — la
      somme des écarts quotidiens ne l'est pas : un écart n'est calculé qu'entre deux
      jours consécutifs, et les journées non collectées sont écartées pour de bon.
      Mesuré le 2026-09-11 sur l'artiste 1, du 2025-01-01 au 2026-06-12 : cette somme
      rendait **21** vues YouTube quand le compteur passait de 99 594 à 118 219, soit
      **18 625** — un facteur 887. Le PDF imprimait les deux sur la même page, la
      courbe à 118 000 et le bâton à 21.

      La croissance d'un compteur sur une fenêtre n'a pourtant besoin d'aucune
      attribution : c'est son NIVEAU à la fin moins son niveau au début. Savoir quel
      jour elle a eu lieu est ce qu'on ignore, et ce n'est pas la question posée. On
      lit donc la série cumulée de la couche or, aux deux bornes.

      Zéro mesure rend `None` — jamais `0`, qui affirmerait qu'il ne s'est rien passé.

    Apple suit sa propre règle dans les deux cas (`apple_lifetime_plays` /
    `apple_period_plays`) : ses relevés sont des totaux de période qui s'imbriquent.
    """
    if db is None or artist_id is None:
        return {}

    if since is not None:
        series = daily_streams_by_platform(db, artist_id)
        levels = cumulative_by_platform(db, artist_id)
        out = {}
        for key in ("spotify", "youtube", "soundcloud"):
            if not measured_days(series, key, since, until):
                out[key] = None
                continue
            rows = levels.get(key)
            if rows:
                # Un COMPTEUR : sa croissance sur la fenêtre est la différence de ses
                # niveaux. Le niveau de départ est le dernier relevé AVANT la fenêtre
                # quand il y en a un — sinon le premier relevé dedans, et la première
                # journée observée ne compte alors pour aucune croissance, ce qui est
                # la seule chose honnête à dire d'une plateforme qu'on venait de
                # commencer à mesurer.
                inside = [(d, v) for d, v in rows if since <= d <= until]
                if not inside:
                    out[key] = None
                    continue
                before = [v for d, v in rows if d < since]
                start = before[-1] if before else inside[0][1]
                out[key] = max(inside[-1][1] - start, 0)
                continue
            out[key] = sum(v for d, v in series.get(key, []) if since <= d <= until)
        out["apple"] = apple_period_plays(db, artist_id, since, until)
        return out

    return {
        "spotify": _lifetime(db, _SQL_LIFETIME, artist_id, "spotify"),
        "youtube": _lifetime(db, _SQL_LIFETIME, artist_id, "youtube"),
        "soundcloud": _lifetime(db, _SQL_LIFETIME, artist_id, "soundcloud"),
        "apple": apple_lifetime_plays(db, artist_id),
    }


def combined_total(totals: dict) -> int:
    """La somme des plateformes MESURÉES. Une absence ne compte pas pour zéro."""
    return sum(v for v in (totals or {}).values() if v)


# LA COUCHE OR (ADR-019, migration 097). Ces trois requêtes étaient trois copies de la
# règle de chaque plateforme ; elles lisent désormais la définition unique. La règle
# elle-même n'a pas changé — la vue porte exactement ce que ces constantes portaient —
# mais elle n'existe plus qu'à UN endroit, et l'API comme le PDF peuvent la lire sans
# recopier le `DISTINCT ON`.
_SQL_LIFETIME = """
    SELECT COALESCE(total, 0)::bigint FROM v_platform_totals
     WHERE artist_id = %s AND platform = %s
"""

_SQL_LIFETIME_SPOTIFY = _SQL_LIFETIME
_SQL_LIFETIME_YOUTUBE = _SQL_LIFETIME
_SQL_LIFETIME_SOUNDCLOUD = _SQL_LIFETIME


def _lifetime(db, sql: str, artist_id, platform: str = "spotify") -> int:
    try:
        row = _q(db, sql, (artist_id, platform))
        return int(row[0][0] or 0) if row else 0
    except Exception as exc:      # noqa: BLE001 — une tuile ne fait pas tomber la page
        logger.warning("lifetime total unavailable: %s", type(exc).__name__)
        return 0
