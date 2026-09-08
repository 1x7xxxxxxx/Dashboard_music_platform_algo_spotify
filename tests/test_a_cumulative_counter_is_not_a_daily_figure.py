"""Guard: un compteur cumulatif ne se trace pas comme une quantité du jour.

Type: Utility
Uses: src.dashboard.utils.platform_timeseries, sqlite3
Triggers: pytest
Persists in: nothing

Error class `a-cumulative-counter-charted-as-a-daily-figure`.

La figure « tes écoutes par jour » additionnait `s4a_song_timeline.streams` (une
quantité du JOUR) et `soundcloud_tracks_daily.playback_count` (le total d'un titre
DEPUIS TOUJOURS). Mesuré en production le 2026-09-08 sur l'artiste 1 : **23 560
« écoutes » le 8 septembre**, et le même chiffre chaque jour, à côté d'un maximum réel
de 1 605 streams/jour côté Spotify. Signalé « les datas sont incohérentes ».

Les trois cas de ce fichier sont les trois artefacts RÉELLEMENT observés ce jour-là,
pas des cas d'école. Chacun ferait dessiner un pic qui n'a pas eu lieu :

1. **une collecte ratée qui écrit 0** — le 2026-06-01, les 19 titres SoundCloud de
   l'artiste 1 valaient 0. L'écart pris sur la veille attribuait toute la remontée au
   jour suivant : 23 480 écoutes le 2026-06-05 ;
2. **un trou de collecte** — 104 jours entre le 2025-12-16 et le 2026-03-30 : les 163
   écoutes gagnées entre-temps ne sont pas celles du 30 mars ;
3. **plusieurs vidéos (ou chaînes) pour un locataire** — l'écart doit se prendre par
   ENTITÉ avant d'additionner, sinon le cumul entier d'une vidéo apparaît le jour de sa
   première collecte. Le bac à sable portait trois `channel_id`, dont un d'un onboarding
   abandonné à 155 vues : un `MAX` toutes entités confondues sautait de 155 à 120 627 et
   affichait 120 472 vues en une journée.

Le test tourne sur un vrai moteur SQL (sqlite) plutôt que sur un faux : les trois
règles VIVENT dans le SQL (`MAX … OVER`, `jour - veille = 1`, `PARTITION BY`), et un
stub Python qui rendrait des lignes toutes faites ne testerait que le stub.
"""
from __future__ import annotations

import datetime as _dt
import sqlite3

import pytest

from src.dashboard.utils import platform_timeseries as pts


class _SqliteDB:
    """Traduit le dialecte Postgres du module vers sqlite, et rien d'autre.

    Les différences sont mécaniques et n'altèrent aucune des règles testées : le
    paramètre `%s`, les casts `::date`/`::bigint`, la soustraction de dates
    (`julianday`), et `GREATEST(a, b)` qui s'écrit `MAX(a, b)` en sqlite — sans cette
    dernière, la requête lève, `_rows` rattrape et rend une liste vide : le test
    passerait au vert sur un moteur qui n'a rien exécuté.
    """

    def __init__(self, path=":memory:") -> None:
        self.conn = sqlite3.connect(path)

    def execute(self, sql, params=()):
        self.conn.execute(sql, params)
        self.conn.commit()

    def fetch_query(self, sql, params=()):
        sql = (sql.replace("%s", "?")
                  .replace("collected_at::date", "date(collected_at)")
                  .replace("::bigint", "").replace("::date", "")
                  .replace("jour - veille = 1", "julianday(jour) - julianday(veille) = 1")
                  .replace("GREATEST(", "MAX("))
        return [tuple(r) for r in self.conn.execute(sql, params).fetchall()]


def _sc_db(rows):
    """rows = [(jour, track_id, playback_count)]"""
    db = _SqliteDB()
    db.execute("CREATE TABLE soundcloud_tracks_daily "
               "(artist_id INT, track_id TEXT, playback_count INT, collected_at TEXT)")
    for jour, track, count in rows:
        db.execute("INSERT INTO soundcloud_tracks_daily VALUES (?,?,?,?)",
                   (1, track, count, jour))
    return db


def _yt_db(rows):
    """rows = [(jour, video_id, view_count)]

    `youtube_video_stats` et non `youtube_channel_history` : le compteur de CHAÎNE
    donnait des chiffres faux — figé onze jours puis +360 attribués à une seule
    journée, contre 64 vues annoncées par YouTube Studio sur la période. La somme des
    compteurs PAR VIDÉO suit le même ordre de grandeur que Studio (44 sur 28 jours).
    """
    db = _SqliteDB()
    db.execute("CREATE TABLE youtube_video_stats "
               "(artist_id INT, video_id TEXT, view_count INT, collected_at TEXT)")
    for jour, video, views in rows:
        db.execute("INSERT INTO youtube_video_stats VALUES (?,?,?,?)",
                   (1, video, views, jour))
    return db


def _series(db, sql, params):
    """Passe par `_rows` — le vrai chemin — mais REFUSE son filet.

    `_rows` avale toute exception parce qu'une courbe absente vaut mieux qu'une page
    qui plante. Dans un test, ce filet transforme une requête cassée en « aucun
    point », c'est-à-dire en vert sur du vide. On exécute donc d'abord la requête à nu.
    """
    db.fetch_query(sql, params)      # lève si le SQL est invalide sur ce moteur
    return dict(pts._rows(db, sql, params))


def test_a_failed_collection_that_wrote_zero_creates_no_spike() -> None:
    """L'artefact du 2026-06-01 : 0 écrit par une collecte ratée, puis la vraie valeur.

    Sans la règle du maximum déjà vu, le 03 vaudrait 23 480 — le cumul entier.
    """
    rows = [("2026-05-30", "t1", 23470), ("2026-05-31", "t1", 23475),
            ("2026-06-01", "t1", 0), ("2026-06-02", "t1", 23480)]
    got = _series(_sc_db(rows), pts._SQL_SOUNDCLOUD, (1,))
    assert got.get("2026-06-01") == 0, "la fausse chute doit valoir 0, jamais un négatif"
    assert got.get("2026-06-02") == 5, (
        f"la remontée après une collecte à zéro est comptée comme de l'activité : "
        f"{got.get('2026-06-02')} au lieu de 5 (23480 − 23475, le maximum déjà vu)")


def test_a_gap_in_collection_produces_no_point_at_all() -> None:
    """104 jours sans mesure : le gain n'appartient à aucun jour, donc aucun point.

    Un zéro affirmerait « aucune écoute » ; un trou dit « on ne sait pas », qui est
    vrai. Les deux se dessinent différemment, et c'est tout l'intérêt.
    """
    rows = [("2025-12-16", "t1", 23241), ("2026-03-30", "t1", 23404),
            ("2026-03-31", "t1", 23410)]
    got = _series(_sc_db(rows), pts._SQL_SOUNDCLOUD, (1,))
    assert "2026-03-30" not in got, (
        f"le jour qui suit un trou de 104 jours porte un point ({got.get('2026-03-30')}) : "
        "104 jours de gain y sont attribués comme s'ils étaient d'un seul jour")
    assert got.get("2026-03-31") == 6, "le lendemain, consécutif, doit valoir son écart"


def test_two_channels_are_two_series_not_one_maximum() -> None:
    """L'artefact du bac à sable : trois entités, dont une à 155 vues.

    Un `MAX(view_count)` toutes chaînes confondues passait de 155 à 120 627 et
    affichait 120 472 vues en une journée. Ce n'était pas une journée.
    """
    rows = [("2026-09-05", "abandonnee", 155),
            ("2026-09-06", "vraie", 120627), ("2026-09-06", "autre", 2664),
            ("2026-09-07", "vraie", 120987), ("2026-09-07", "autre", 2665)]  # noqa: E501
    got = _series(_yt_db(rows), pts._SQL_YOUTUBE, (1,))
    assert got.get("2026-09-06") is None, (
        "le premier jour d'une chaîne ne peut pas porter d'écart")
    assert got.get("2026-09-07") == 361, (
        f"les chaînes sont mélangées : {got.get('2026-09-07')} au lieu de 361 "
        "(360 sur la vraie chaîne + 1 sur l'autre)")


def test_the_combined_total_never_counts_an_absence_as_a_zero() -> None:
    """Un jour qu'une seule plateforme a mesuré vaut sa mesure, pas sa mesure moins rien.

    Additionner un zéro d'absence ferait baisser le total le jour où une source n'a
    pas tourné — ce qui se lit comme une chute d'écoutes.
    """
    d = _dt.date
    series = {"spotify": [(d(2026, 9, 1), 40), (d(2026, 9, 2), 50)],
              "youtube": [(d(2026, 9, 2), 7)]}
    assert pts.combined_daily_streams(series) == [(d(2026, 9, 1), 40), (d(2026, 9, 2), 57)]


def test_apple_exists_only_at_the_yearly_step() -> None:
    """Apple a une série depuis les migrations 093/094 — mais à un seul pas.

    Ses exports sont des totaux de PÉRIODE. Étaler 900 écoutes de 2024 sur 366 jours
    inventerait une valeur quotidienne que personne n'a mesurée : c'est la faute que ce
    module existe pour empêcher. Au pas annuel, en revanche, « 2024 » est exactement un
    point.
    """
    assert pts.STEP_ONLY.get("apple") == "year", (
        "Apple n'est plus restreinte au pas annuel : elle va être étalée sur des jours "
        "qu'aucun relevé ne mesure")
    assert "apple" in pts.PLATFORM_LABELS, "Apple a disparu des libellés"


@pytest.mark.parametrize("platform", sorted(pts.PLATFORM_LABELS))
def test_every_charted_platform_has_a_colour(platform) -> None:
    """UNE seule palette, celle du rendu.

    `platform_timeseries` en portait une COPIE (`PLATFORM_COLORS`) qui n'a pas suivi
    l'ajout d'Apple : deux constantes pour une question, la dérive exacte que le garde
    de l'illustration dénonce. Retirée le 2026-09-08 ; la palette vit dans
    `platform_chart`, et ce test la lit là.
    """
    from src.dashboard.utils import platform_chart as pc
    assert pc._PALETTE_LIGHT.get(platform), platform
    assert pc._PALETTE_DARK.get(platform), platform


def test_youtube_reads_per_video_counters_not_the_channel_one() -> None:
    """La SOURCE, épinglée — c'est elle qui donnait des chiffres faux.

    `youtube_channel_history.view_count` est mis à jour par PALIERS et porte autre
    chose que la somme des vidéos : mesuré le 2026-09-08, figé à 120 627 pendant onze
    jours puis 120 987, soit +360 attribués à une seule journée. YouTube Studio
    annonçait **64 vues** sur la période ; la somme des compteurs par vidéo en donnait
    44 sur 28 jours — le bon ordre de grandeur.

    Lu sur la structure de la requête, pas sur son texte : ce fichier NOMME les deux
    tables dans sa documentation.
    """
    import re
    tables = set(re.findall(r"FROM\s+([a-z_]+)", pts._SQL_YOUTUBE))
    assert "youtube_video_stats" in tables, (
        f"la série YouTube ne lit pas les compteurs par vidéo : {sorted(tables)}")
    assert "youtube_channel_history" not in tables, (
        "la série YouTube est revenue au compteur de CHAÎNE, qui saute par paliers et "
        "attribue des centaines de vues à une seule journée")
    assert "PARTITION BY video_id" in pts._SQL_YOUTUBE, (
        "l'écart n'est pas pris par vidéo : le cumul entier d'une vidéo apparaîtra le "
        "jour de sa première collecte")
