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

    Ne lève jamais : cette figure est décorative, et une page de bienvenue qui plante
    sur un `SELECT` coûte infiniment plus que trois exemples.
    """
    if db is None or artist_id is None:
        return []
    sql = """
        SELECT d::date AS jour, SUM(v)::bigint AS ecoutes FROM (
            SELECT date AS d, streams AS v
              FROM s4a_song_timeline
             WHERE artist_id = %s AND song NOT ILIKE '%%1x7xxxxxxx%%'
            UNION ALL
            SELECT collected_at::date AS d, playback_count AS v
              FROM soundcloud_tracks_daily
             WHERE artist_id = %s
        ) t
        WHERE d IS NOT NULL AND v IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """
    try:
        return list(db.fetch_query(sql, (artist_id, artist_id)) or [])
    except Exception:      # noqa: BLE001 — décoratif : on retombe sur l'exemple
        return []


def figure_source(rows: list[tuple]) -> Source:
    """`tenant` seulement si la série dit quelque chose. Sinon `example`.

    Rendue séparément du tracé pour que l'appelant décide du LIBELLÉ avec la même
    fonction qui décide de la courbe : c'est ce qui empêche d'afficher les chiffres
    d'un artiste sous le mot « Exemple », et l'inverse.
    """
    return "tenant" if len(rows) >= MIN_POINTS else "example"
