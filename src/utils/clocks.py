"""Quelle horloge a produit cette date — déclaré une fois, pour toutes les surfaces.

Type: Utility
Uses: nothing (pures constantes + fonctions)
Triggers: src/dashboard/utils/platform_timeseries.py, les vues de période
Persists in: nothing

La cause, et pourquoi elle est restée ouverte le plus longtemps
---------------------------------------------------------------
L'audit du 2026-09-10 a nommé sept causes aux incohérences de la figure d'accueil. Six
ont été corrigées le jour même. La septième — « aucune horloge n'est déclarée » — est
restée entière, parce qu'elle n'est pas un défaut mais une ABSENCE : quatre horloges
cohabitent sur le même axe et rien, nulle part, ne dit laquelle a produit une date
donnée. Tant qu'une date circule sans dire d'où elle vient, chaque comparaison de
période repose sur une supposition qu'on ne peut ni vérifier ni réfuter.

Ce fichier est la déclaration manquante. Il ne convertit rien et ne corrige rien : il
REND EXPLICITE ce que chaque colonne veut dire, pour qu'une supposition devienne une
propriété qu'un test peut tenir.

Ce que la mesure a dit, et qui a réduit le chantier
---------------------------------------------------
Mesuré en production le 2026-09-10, et ce comptage a corrigé mon propre constat :

* `collected_at` post-migration-019 (l'ère actuelle) : sur YouTube, **0 ligne sur
  5 807** change de jour selon le fuseau retenu. Les collectes nocturnes atterrissent
  à 10 h UTC, à plus de quatre heures de toute frontière de jour ;
* toutes plateformes confondues, **29 lignes** basculent, et ce sont des collectes
  DÉCLENCHÉES À LA MAIN tard dans la journée (jusqu'à 23 h UTC) ;
* les 267 lignes YouTube « qui basculent » que j'avais comptées sont **pré-019**,
  c'est-à-dire des `DATE` — un jour calendaire, pas un instant. Leur appliquer une
  conversion de fuseau ne les corrige pas : ça les déplace d'un jour sans raison.

J'avais écrit « 200 lignes sur 2 535, 7,9 % » dans le catalogue d'erreurs. Ce chiffre
mélangeait les deux ères sur une base locale. Le chiffre juste est ci-dessus.

La conséquence est le seul vrai risque de cette zone : **le danger n'est pas de laisser
`collected_at` tel quel, c'est de le « corriger »**. Une conversion de fuseau appliquée
à une colonne naïve déplacerait 267 jours calendaires déjà justes. D'où le garde
`tests/test_a_naive_timestamp_is_not_reinterpreted.py`, qui interdit exactement ça.
"""
from __future__ import annotations

# Le fuseau dans lequel le produit se LIT. N'entre jamais dans un calcul de mesure —
# seulement dans l'affichage (voir `src/dashboard/utils/tz.py`).
DISPLAY_TZ = "Europe/Paris"

# L'horloge qui décide d'un JOUR DE MESURE. Les collecteurs écrivent
# `datetime.now(timezone.utc)` ; un jour de mesure est donc un jour UTC, et ça ne
# dépend pas du poste qui affiche.
MEASUREMENT_TZ = "UTC"


class Clock:
    """Les quatre horloges, nommées. Une date appartient à exactement une d'elles."""

    #: Écrite par NOS collecteurs au moment de la collecte. Instant, UTC.
    OURS = "ours"
    #: Lue dans un fichier déposé par l'artiste (colonne du CSV Spotify for Artists).
    #: Jour calendaire dans le fuseau de publication de la plateforme — inconnu de nous.
    PUBLISHER_FILE = "publisher-file"
    #: Lue dans le NOM d'un fichier exporté (période Apple Music). Jour calendaire,
    #: fuseau de publication d'Apple.
    PUBLISHER_FILENAME = "publisher-filename"
    #: Choisie par l'artiste dans un sélecteur de période. Jour calendaire, fuseau
    #: d'affichage.
    READER = "reader"


# La déclaration, par nom de colonne. Le nom est le bon niveau : la même colonne porte
# la même horloge dans les 51 tables où elle apparaît, et c'est justement ce qu'on veut
# pouvoir affirmer.
COLUMN_CLOCK: dict[str, str] = {
    "collected_at": Clock.OURS,
    "snapshot_date": Clock.OURS,
    "run_date": Clock.OURS,
    "day_date": Clock.OURS,          # Meta rend le jour de SA journée publicitaire
    "prediction_date": Clock.OURS,
    "date": Clock.PUBLISHER_FILE,    # s4a_song_timeline et ses voisines
    "reporting_date": Clock.PUBLISHER_FILE,
    "line_date": Clock.PUBLISHER_FILE,
    "period_start": Clock.PUBLISHER_FILENAME,
    "period_end": Clock.PUBLISHER_FILENAME,
    "release_date": Clock.PUBLISHER_FILE,
    "published_at": Clock.PUBLISHER_FILE,
}


def clock_of(column: str) -> str | None:
    """L'horloge déclarée pour cette colonne, ou None si elle n'est pas déclarée."""
    return COLUMN_CLOCK.get(column)


def is_convertible(column: str) -> bool:
    """Cette date peut-elle légitimement changer de fuseau ?

    Non pour tout ce qui vient d'un éditeur : un jour calendaire lu dans un fichier
    n'est PAS un instant, il n'y a rien à convertir. Le convertir quand même est la
    seule façon connue de casser cette zone — mesuré : 267 jours déjà justes seraient
    déplacés d'un jour.
    """
    return clock_of(column) == Clock.OURS


# L'écart qu'on ne peut pas corriger, et qu'on NOMME plutôt que de l'effacer : la
# journée de reporting de Spotify et celle d'Apple ne sont pas définies dans notre
# fuseau, et aucune des deux ne publie le sien. Un total « du 1er au 31 » peut donc
# différer du leur de quelques heures aux bords. Cette phrase s'affiche là où deux
# sources d'horloges différentes sont additionnées.
UNRECONCILABLE_NOTE = (
    "Les journées de Spotify et d'Apple sont arrêtées dans leur propre fuseau, qu'ils "
    "ne publient pas : aux bords d'une période, quelques heures peuvent tomber d'un "
    "côté ou de l'autre. L'écart n'est pas corrigeable — il est nommé ici plutôt "
    "qu'effacé."
)

# ── Ce que la date DATE, ce qui n'est pas la même question que « quelle horloge » ──
#
# `COLUMN_CLOCK` ci-dessus dit QUI a produit la date. Il reste à dire de QUOI elle est
# la date — et c'est cette seconde question qui décide si une figure bornée sur elle
# répond à ce qu'elle annonce.
#
# Le cas qui a fait naître cette table, mesuré le 2026-09-10 : Instagram bornait sa
# figure « Engagement par mois » sur `timestamp`, la date de PUBLICATION du post,
# alors que `like_count` est un compteur cumulé lu aujourd'hui. La barre de janvier
# portait donc les likes donnés en juin à un post de janvier. Le filtre était appliqué,
# la borne portait sur la mauvaise chose, et aucun garde ne pouvait le voir : tous
# vérifiaient QUE la fenêtre est appliquée, aucun SUR QUOI.


class Dates:
    """De quoi une colonne de date est la date."""

    #: Le moment où la chose s'est produite. Une figure « sur la période » veut ça.
    EVENT = "event"
    #: Le moment où NOUS avons relevé la valeur. Pour un compteur cumulé, c'est la
    #: seule date disponible, et elle date la MESURE, pas l'écoute.
    MEASUREMENT = "measurement"
    #: Le moment où l'entité est SORTIE. Borner dessus construit une COHORTE — un
    #: regroupement parfaitement légitime, mais qui ne répond pas à « que s'est-il
    #: passé sur la période ». Il doit être annoncé comme tel.
    PUBLICATION = "publication"


COLUMN_SUBJECT: dict[str, str] = {
    "date": Dates.EVENT,                 # s4a, hypeddit, apple : le jour rapporté
    # `day` est la colonne de date des VUES de la couche or — `v_s4a_song_daily`,
    # `v_platform_levels`. Elle porte le MÊME sujet que la colonne dont elle dérive :
    # le jour que la plateforme rapporte, pas celui où nous l'avons lu. Ajoutée le
    # 2026-09-12 avec la migration 105, quand les surfaces ont cessé de lire la table
    # de fait — sans cette déclaration, une figure bornée sur la couche or ne pouvait
    # plus dire de quoi elle parle.
    "day": Dates.EVENT,
    "day_date": Dates.EVENT,             # Meta : sa journée publicitaire
    "reporting_date": Dates.EVENT,
    "line_date": Dates.EVENT,
    "snapshot_date": Dates.MEASUREMENT,
    "collected_at": Dates.MEASUREMENT,
    "run_date": Dates.MEASUREMENT,
    "prediction_date": Dates.MEASUREMENT,
    "period_start": Dates.EVENT,
    "period_end": Dates.EVENT,
    "timestamp": Dates.PUBLICATION,      # instagram_media : la sortie du post
    # `month` est la colonne de `v_instagram_media_monthly`, qui regroupe les posts
    # par mois de PUBLICATION. Elle hérite donc du sujet de `timestamp` : borner
    # dessus construit une cohorte de posts, pas une période d'activité — et c'est
    # exactement ce que la vue nomme dans son commentaire.
    "month": Dates.PUBLICATION,
    "published_at": Dates.PUBLICATION,
    "release_date": Dates.PUBLICATION,
    "track_created_at": Dates.PUBLICATION,
}


def subject_of(column: str) -> str | None:
    """De quoi cette colonne est la date, ou None si elle n'est pas déclarée."""
    return COLUMN_SUBJECT.get(column)


def is_cohort_column(column: str) -> bool:
    """Borner là-dessus regroupe par date de SORTIE, pas par période d'activité.

    Ce n'est pas une faute — c'est une lecture différente, et souvent la seule
    possible. Mais elle doit être ANNONCÉE : « likes acquis à ce jour, par mois de
    publication » et « engagement par mois » ne disent pas la même chose, et seul le
    second se lit comme un flux.
    """
    return subject_of(column) == Dates.PUBLICATION
