"""D'où vient la fraîcheur d'une source — déclaré UNE fois, lu par deux surfaces.

Type: Utility
Uses: rien (stdlib pure — il doit s'importer depuis un DAG ET depuis Streamlit)
Depends on: nothing
Triggers: src/dashboard/utils/kpi_helpers.py, src/utils/freshness_monitor.py
Persists in: nothing

Le défaut, mesuré le 2026-09-22
--------------------------------
Deux registres nommaient les mêmes sources, chacun avec sa propre copie de la table et
de la colonne où lire la fraîcheur :

    src/dashboard/utils/kpi_helpers.py   SOURCES_CONFIG    la grille de l'accueil
    src/utils/freshness_monitor.py       MONITOR_TARGETS   l'alerte nocturne

Sept des huit sources y portaient les mêmes valeurs. **La huitième, iMusician, n'était
que dans le premier** — elle pouvait donc se périmer indéfiniment sans qu'aucune alerte
ne le dise. Hypeddit et SACEM, eux, n'étaient dans ni l'un ni l'autre alors que leurs
tables existent en production.

C'est la classe « un catalogue recopié », que ce dépôt a payée quatre fois. Enrichir un
seul des deux registres — ce que la refonte de l'accueil demandait — en aurait fait une
troisième divergence.

Ce que ce module déclare, et ce qu'il NE déclare PAS
-----------------------------------------------------
Il déclare le **tronc commun** : pour chaque source, l'identifiant, la table et la
colonne qui datent sa dernière mesure, et si elle est nourrie par une collecte ou par
un dépôt de fichier. C'est le strict nécessaire pour que les deux lecteurs parlent de la
même chose.

Il ne déclare PAS ce qui appartient à un seul lecteur :

    l'accueil          l'icône, l'heure annoncée, le geste, la page cible
    l'alerte nocturne  le seuil d'ancienneté, le silence légitime, la colonne de MESURE

⚠️ **Et il ne fusionne surtout pas la question par locataire.** Pour Spotify, les deux
surfaces interrogent volontairement deux tables différentes : l'accueil lit `artists` à
travers le pont `saas_artists.spotify_artist_id`, l'alerte lit
`track_popularity_history`. Ce n'est pas une divergence, c'est une décision écrite dans
`freshness_monitor` — « quatre surfaces jugeaient Spotify sur quatre tables
différentes », et le remède fut de nommer la bonne pour chaque question, pas d'en
imposer une seule. Le tronc commun s'arrête donc là où la question change.
"""
from __future__ import annotations

from typing import NamedTuple


class Source(NamedTuple):
    """Le tronc commun d'une source de données.

    `cle`     — l'identifiant stable, celui que les deux registres partagent.
    `table`   — où lire la dernière mesure, à l'échelle de la flotte.
    `col`     — la colonne d'horodatage d'ÉCRITURE.
    `fed_by`  — `"api"` (une collecte part toute seule) ou `"csv"` (un dépôt humain).

    ⚠️ `col` est la date d'ÉCRITURE, pas celle que la donnée DÉCRIT. La différence a
    coûté cher : le 2026-08-21, `meta_insights_performance_day` portait un
    `MAX(collected_at)` du matin même et un `MAX(day_date)` au **2024-09-30**. Le DAG
    tournait et ré-écrivait les mêmes lignes vieilles de deux ans ; toute sonde qui
    lisait l'horodatage d'écriture la déclarait fraîche. Meta était mort depuis début
    août derrière un feu vert. La colonne de MESURE reste donc déclarée chez l'alerte,
    qui est la surface qui en a besoin.
    """

    cle: str
    table: str
    col: str
    fed_by: str
    #: La colonne que la donnée DÉCRIT, quand la table la porte à côté de la date
    #: d'écriture. `None` quand `col` EST la date de mesure (un instantané : les
    #: abonnés d'aujourd'hui, les titres d'aujourd'hui).
    #:
    #: ⚠️ ELLE EST DESCENDUE ICI LE 2026-09-22, et c'est une propriété de la TABLE,
    #: pas d'un lecteur. Elle vivait chez l'alerte nocturne « qui est la surface qui
    #: en a besoin » — puis une deuxième en a eu besoin (`admin § Technique`, qui
    #: écrivait huit requêtes à la main pour lire `MAX(date)` et `MAX(day_date)`).
    #: Deux lecteurs, donc elle descend. Même geste que `MIN_DEPENSE` le matin même.
    metric_col: str | None = None

    #: La colonne qui porte le LOCATAIRE dans cette table. `None` quand la table n'est
    #: pas scopée par l'identifiant SaaS et qu'il faut un pont — voir `artist_filter`.
    #:
    #: ⚠️ ELLE DESCEND ICI LE 2026-09-22, pour la raison exacte de `metric_col` :
    #: un TROISIÈME lecteur en a eu besoin, et il ne pouvait pas aller la chercher.
    #: `src/utils/activation.py` comptait la livraison sur
    #: `etl_run_log.rows_inserted > 0`, et ce compteur MENT — mesuré en production le
    #: 2026-09-22 : l'artiste 12 porte **32 exécutions `success` à 0 ligne** sur
    #: YouTube et **95 lignes fraîches du jour** dans
    #: `youtube_channel_history`. Répondre « cette plateforme a-t-elle livré ? »
    #: demande donc de lire la TABLE DE DONNÉES, et la lire par locataire demande
    #: cette colonne. Elle vivait dans `kpi_helpers.SOURCES_CONFIG`, que
    #: `activation.py` ne peut pas importer : il est lu par un DAG, et un module de
    #: `src/utils/` qui importe le tableau de bord est la violation de couche déjà
    #: payée le matin même (`meta_axes` → une vue, 1 073 ms au premier rendu).
    artist_col: str | None = "artist_id"

    #: Le PONT, quand `artist_col` est `None` : une clause SQL complète qui scope la
    #: table sur le locataire, avec un `%s` pour son identifiant. Constante de
    #: confiance (aucune entrée utilisateur), validée contre une allowlist avant
    #: interpolation — règle transverse 8.
    artist_filter: str | None = None


#: Les sources connues du produit. L'ORDRE n'a pas de sens ici — chaque lecteur trie
#: selon sa propre question (l'accueil par ce qui a des données, l'alerte par gravité).
SOURCES: tuple[Source, ...] = (
    # `artists` a pour clé l'identifiant Spotify (VARCHAR), pas le locataire SaaS.
    # Le pont passe par `saas_artists.spotify_artist_id` : un compte non relié ne
    # matche RIEN, donc il lit « pas de données » au lieu d'hériter de la
    # fraîcheur d'un autre locataire. C'est `artist_id n'est pas toujours le
    # locataire` de `.claude/rules/python.md`, appliqué au registre.
    Source("Spotify API", "artists", "collected_at", "api", artist_col=None,
           artist_filter="artist_id IN (SELECT spotify_artist_id FROM saas_artists "
                         "WHERE id = %s)"),
    Source("Spotify S4A", "s4a_song_timeline", "collected_at", "csv", "date"),
    Source("YouTube", "youtube_channel_history", "collected_at", "api"),
    Source("SoundCloud", "soundcloud_tracks_daily", "collected_at", "api"),
    Source("Instagram", "instagram_daily_stats", "collected_at", "api"),
    # `snapshot_date` (migration 093) est la date que l'export Apple PORTE. Elle
    # égalait `collected_at` au 2026-09-22 — 29 lignes sur 29, toutes au 08/09 —
    # donc l'écart était LATENT, et un garde l'avait nommé comme tel de longue
    # date. Le déclarer le rend nul par construction : un export de la semaine
    # dernière déposé aujourd'hui cesserait de compter comme frais.
    # `period_end` (094) existe aussi mais vaut NULL partout : inutilisable.
    Source("Apple Music", "apple_songs_performance", "collected_at", "csv",
           "snapshot_date"),
    Source("Meta Ads", "meta_insights_performance_day", "collected_at", "api", "day_date"),
    Source("iMusician", "imusician_monthly_revenue", "updated_at", "csv"),
    # ── Entrées le 2026-09-22 : leurs tables existent en production depuis des mois
    # et AUCUN des deux registres ne les connaissait. Ni l'accueil ni l'alerte ne
    # pouvaient donc dire qu'elles étaient vides ou périmées.
    # `updated_at` et non `created_at` : une saisie manuelle se CORRIGE, et la
    # corriger est un signe de vie. Même choix que iMusician ci-dessus.
    Source("Hypeddit", "hypeddit_daily_stats", "updated_at", "csv", "date"),
    Source("SACEM", "sacem_statement", "created_at", "csv", "line_date"),
)

#: Index par clé, pour qui a une clé et veut la source.
PAR_CLE: dict[str, Source] = {s.cle: s for s in SOURCES}


def colonne_de_mesure(cle: str) -> str:
    """La colonne à lire pour savoir de QUAND la donnée parle.

    Rend `metric_col` quand la table en porte une, sinon `col`. C'est LA question
    qu'une surface de fraîcheur pose, et la confondre avec la date d'écriture a
    coûté **718 jours** sur `meta_insights_performance_day` : le DAG ré-écrivait
    des lignes de 2024 chaque matin, et toute sonde lisant `collected_at` les
    déclarait fraîches. Meta était mort depuis six semaines derrière un feu vert.
    """
    s = PAR_CLE.get(cle)
    if s is None:
        raise KeyError(f"source inconnue : {cle!r}")
    return s.metric_col or s.col


def table_et_colonne(cle: str) -> tuple[str, str]:
    """Où lire la dernière mesure de cette source. Lève si la clé est inconnue.

    Lève plutôt que de rendre un défaut : une source qu'on ne connaît pas n'a pas de
    table plausible, et en inventer une ferait lire la fraîcheur de quelqu'un d'autre.
    """
    s = PAR_CLE.get(cle)
    if s is None:
        raise KeyError(
            f"source inconnue : {cle!r}. Les sources connues sont "
            f"{sorted(PAR_CLE)} — ajoute-la ici, et les deux lecteurs la verront.")
    return s.table, s.col
