"""La première figure de l'écran de bienvenue, tirée des données du locataire.

Type: Sub
Uses: PostgresHandler (passé, jamais ouvert ici)
Depends on: s4a_song_timeline, soundcloud_tracks_daily
Persists in: nothing

R58 — et ce qu'elle attendait vraiment
---------------------------------------
La tâche disait attendre « un locataire qui a des données, donc R1 ». C'était vrai
pour la MOITIÉ qui part par e-mail, et faux pour l'autre :

* le mot de bienvenue est envoyé à la VÉRIFICATION, donc avant toute collecte — il ne
  pourra jamais montrer les chiffres de son destinataire. Il garde ses exemples, et
  ce n'est pas un pis-aller : c'est le seul contenu vrai à cet instant ;
* `kaleido` est absent de toutes les images, donc une figure Plotly ne s'exporte pas
  en PNG côté serveur — deuxième raison pour l'e-mail, aucune pour l'app, qui rend
  Plotly nativement ;
* l'app, elle, affiche cette page à un artiste qui REVIENT par le menu, et celui-là a
  des données. Le mécanisme « la sienne si elle existe, l'exemple sinon » était donc
  écrivable et éprouvable sans attendre R1.

Ce module est cette moitié-là.

Le piège que la tâche nommait d'avance
---------------------------------------
« Un exemple doit continuer à s'annoncer. Le mélange est le vrai piège : une figure
réelle et une figure d'exemple côte à côte, sans que rien ne les distingue, est pire
que trois exemples. »

D'où `figure_source()`, qui renvoie ce qu'il faut ÉCRIRE au-dessus, pas seulement
quoi tracer : `tenant` ou `example`. L'appelant ne peut pas afficher l'une en croyant
l'autre — c'est la même précaution que `test_public_counters_count_humans` ailleurs.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

Source = Literal["tenant", "example"]

# Le minimum pour qu'une courbe dise quelque chose. Sous ce seuil, deux points reliés
# suggèrent une tendance qui n'existe pas — et l'exemple, lui, en montre une vraie.
MIN_POINTS = 7


def tenant_daily_streams(db: Any, artist_id: Optional[int]) -> list[tuple]:
    """(jour, écoutes) du locataire, toutes sources confondues, ordre chronologique.

    Elle portait son PROPRE SQL, et il additionnait deux formes :
    `s4a_song_timeline.streams` (une quantité du jour) et
    `soundcloud_tracks_daily.playback_count` (un compteur CUMULÉ par titre) dans un
    même `UNION ALL`. Le total d'un jour valait donc la somme des écoutes du jour plus
    le cumul de carrière de chaque titre SoundCloud — un chiffre faux qui a l'air juste,
    et le SQL littéral que le catalogue d'erreurs cite comme origine de la classe.

    Il était inoffensif ici parce que son seul appelant n'en lit que le NOMBRE de
    points ; il était public et invitant. `platform_timeseries` sait déjà faire cette
    conversion correctement — chaque source ramenée à des quantités du jour, delta pris
    par entité et seulement entre jours consécutifs. Il n'y a plus de deuxième version.

    Ne lève jamais : cette figure est décorative, et une page de bienvenue qui plante
    sur un `SELECT` coûte infiniment plus que trois exemples.
    """
    if db is None or artist_id is None:
        return []
    from src.dashboard.utils.platform_timeseries import (
        combined_daily_streams, daily_streams_by_platform,
    )
    try:
        return combined_daily_streams(daily_streams_by_platform(db, artist_id))
    except Exception:      # noqa: BLE001 — décoratif : on retombe sur l'exemple
        return []


def figure_source(rows: list[tuple]) -> Source:
    """`tenant` seulement si la série dit quelque chose. Sinon `example`.

    Rendue séparément du tracé pour que l'appelant décide du LIBELLÉ avec la même
    fonction qui décide de la courbe : c'est ce qui empêche d'afficher les chiffres
    d'un artiste sous le mot « Exemple », et l'inverse.
    """
    return "tenant" if len(rows) >= MIN_POINTS else "example"
