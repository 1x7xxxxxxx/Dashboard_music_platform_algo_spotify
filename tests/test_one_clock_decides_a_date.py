"""Deux horloges ne se soustraient pas l'une de l'autre.

Type: Test
Uses: pytest
Depends on: src/dashboard/utils/kpi_helpers.py, src/dashboard/utils/date_range.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
Quatre horloges cohabitaient sur le même écran : la date de publication de Spotify
portée par le fichier déposé, l'heure UTC de nos collectes, la date de publication
d'Apple lue dans un nom de fichier, et l'heure LOCALE de l'hôte pour les bornes de
période choisies par l'artiste.

Deux conséquences, chiffrées sur les vraies données :

* `freshness_status` faisait `datetime.now() - last_dt` — une heure locale moins un
  horodatage UTC. Tous les âges de fraîcheur étaient faux d'une heure l'hiver, de deux
  l'été : une source collectée il y a 23 h s'affichait « il y a 25 h » et basculait de
  vert à orange sans que rien n'ait vieilli.
* **200 lignes sur 2 535** de `youtube_video_stats` (7,9 %) changent de JOUR selon le
  fuseau retenu — 19 sur 349 pour SoundCloud. Et c'est la date qui décide si deux
  relevés sont consécutifs, donc si l'écart quotidien est gardé ou jeté.

Ce que ce garde NE prétend pas fermer
--------------------------------------
Il ne réconcilie pas les fuseaux de publication de Spotify et d'Apple avec les nôtres :
on ne peut pas les corriger, seulement les nommer. Il ferme les deux endroits où NOUS
introduisions une horloge de plus.
"""
from __future__ import annotations

import datetime as dt

from src.dashboard.utils import date_range
from src.dashboard.utils.kpi_helpers import freshness_status


def test_a_naive_timestamp_is_read_as_utc_not_as_local_time() -> None:
    """23 h doit s'afficher 23 h, quel que soit le fuseau de la machine qui affiche."""
    naive_utc = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(hours=23)
    emoji, _, label = freshness_status(naive_utc)
    assert "23h" in label, (
        f"« {label} » pour un relevé vieux de 23 h exactement. Une heure locale moins "
        "un horodatage UTC décale l'âge d'une à deux heures — assez pour faire "
        "basculer un voyant de vert à orange sans que rien n'ait vieilli.")
    assert emoji == "🟢", "23 h est en-deçà du seuil de fraîcheur : le voyant doit être vert"


def test_an_aware_timestamp_is_not_shifted_twice() -> None:
    """Un horodatage qui porte DÉJÀ son fuseau ne doit pas être réinterprété."""
    aware = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)
    assert "2h" in freshness_status(aware)[2]


def test_the_period_bounds_follow_the_product_day_not_the_host() -> None:
    """La « journée » du produit est celle de son fuseau d'affichage, déclaré une fois."""
    from zoneinfo import ZoneInfo

    from src.dashboard.utils.tz import DISPLAY_TZ
    expected = dt.datetime.now(ZoneInfo(DISPLAY_TZ)).date()
    assert date_range._today_in_display_tz() == expected

    # Et la borne haute d'une fenêtre glissante EST cette journée-là.
    since, until = date_range.bounds("30d")
    assert until == expected
    assert (until - since).days == 29, "« 30 jours » compte son propre dernier jour"


def test_an_injected_day_still_wins() -> None:
    """Le test doit pouvoir figer le calendrier : sans ça il change d'avis le 1ᵉʳ janvier."""
    assert date_range.bounds("ytd", today=dt.date(2026, 3, 4)) == (
        dt.date(2026, 1, 1), dt.date(2026, 3, 4))
