"""Le taux de clic Hypeddit de l'accueil : ratio des sommes, lien confirmé, jamais zéro.

Type: Test
Uses: pytest, live Postgres
Depends on: src/dashboard/utils/platform_timeseries.py, src/dashboard/views/home.py
Persists in: nothing

Ce qui est demandé (2026-09-13)
-------------------------------
« intègre le meilleur rapport visits/click dans la page d'accueil pour hypeddit
obtenue pour la dernière release ». Hypeddit est dans le cœur du produit (ADR-025) et
n'avait **aucune** occurrence sur l'accueil — la dernière divergence entre cet
arbitrage et l'écran.

Les trois pièges, et pourquoi chacun a son test
-----------------------------------------------
1. **La colonne `ctr` de la table existe, et elle ment sur l'absence.** Son
   déclencheur (`calculate_hypeddit_metrics`, `src/database/hypeddit_schema.py`)
   écrit `0` quand `visits = 0` : un jour non mesuré y est indiscernable d'un jour
   sans clic. L'accueil ne la lit pas — il recalcule sur `v_hypeddit_daily` avec
   `NULLIF`, qui rend `None`.
2. **Le ratio des sommes n'est pas la moyenne des ratios.** Les deux diffèrent dès
   que les jours n'ont pas le même volume, et c'est le premier qui répond à « quel
   taux ce lien a-t-il obtenu ».
3. **Le rapprochement de titre ne peut pas se faire par le nom.** Mesuré : la sortie
   est `Ô Chiotte l'arbitre Tucome Back - Original`, la campagne `Ô Chiotte l'arbitre
   tucome back` — casse ET suffixe diffèrent. Seul `track_platform_link` en
   `confirmed` relie les deux.
"""
from __future__ import annotations

import datetime as _dt
import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


# La porte LÉGÈRE. Le corps recopié ici importait `get_db_connection`
# (**5,30 s**, dont 5,19 s de Streamlit) et ouvrait une connexion À L'IMPORT du
# module, donc à la collecte, une fois par fichier et par worker.
# `tests.db_gate.db_ready` répond en 0,19 s, derrière un `lru_cache` partagé, et
# sonde en plus `DATABASE_URL` et le schéma réel. Le nom est conservé : seuls le
# coût et le nombre de connexions changent.
from tests.db_gate import db_ready as _db_ready  # noqa: E402


# ⚠️ DEUX marques, et la seconde a été ajoutée le 2026-09-16 sur un rouge observé.
#
# `test_the_rate_does_not_follow_the_period_filter` est tombé une fois dans la suite
# complète (`-n auto --dist loadgroup`) et passe seul, cinq fois de suite. La structure
# explique le rouge : `staged_empty_rival` ÉCRIT une campagne rivale sur l'artiste **1**
# de la base partagée, et trois tests de ce même fichier LISENT l'artiste 1. Sans groupe
# xdist, rien n'oblige ces tests à tenir sur le même worker : le lecteur peut donc
# mesurer entre l'insertion de la rivale et son `finally`.
#
# ⚠️ Honnêteté sur la preuve : **la course n'a PAS été reproduite** — le fichier seul en
# `-n 2` est trop court pour collisionner. Ce qui est établi est la STRUCTURE (un
# écrivain et des lecteurs du même locataire, distribuables sur deux workers), pas
# l'enchaînement exact. Le groupe est le remède que `--dist loadgroup` existe pour
# rendre possible, il ne coûte que de la sérialisation, et il n'invente aucune cause.
pytestmark = [
    pytest.mark.skipif(
        not _db_ready(),
        reason=f"No provisioned Postgres on {_DB_HOST}:{_DB_PORT} — needs a live DB"),
    pytest.mark.xdist_group("hypeddit_tenant_1"),
]


@pytest.fixture()
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


def _side(db, artist_id, since=None, until=None) -> dict:
    from src.dashboard.utils.period_side_metrics import period_side_metrics
    return period_side_metrics(db, artist_id, since, until)


# La date sentinelle de la mise en scène. Hors de tout historique réel, et
# reconnaissable si un jour une exécution interrompue en laissait une derrière elle.
_STAGED_DAY = _dt.date(1999, 1, 2)


@pytest.fixture()
def staged_second_day(db):
    """Un SECOND jour mesuré sur la campagne liée — sans lui, ce garde ne garde rien.

    ⚠️ MESURÉ LE 2026-09-13 : **aucune** campagne du parc n'a deux jours à visites
    non nulles. Ratio des sommes et moyenne des ratios y rendent donc le MÊME
    nombre, et le test passait au vert sur la mutation qui remplace l'un par
    l'autre. Un garde qu'on ne peut pas faire rougir ne garde rien — il fallait
    mettre en scène le cas qu'il prétend tenir.

    Les volumes sont choisis pour ÉCARTER les deux formules, pas au hasard : sur
    7 828 visites et 3 581 clics existants, ajouter 10 visites et 9 clics donne
    45,8 pour le ratio des sommes contre 67,9 pour la moyenne des ratios.

    La ligne est retirée dans un `finally`. Une suite a un rayon de souffle, et
    celle-ci écrit dans une vraie base.
    """
    m = _side(db, 1)
    campaign = m.get("hypeddit_campaign")
    if not campaign:
        pytest.skip("aucune campagne Hypeddit liée à la dernière sortie sur cette base")
    db.execute_query(
        "INSERT INTO hypeddit_daily_stats (artist_id, campaign_name, date, "
        "visits, clicks) VALUES (%s, %s, %s, 10, 9) "
        "ON CONFLICT (artist_id, campaign_name, date) DO UPDATE "
        "SET visits = 10, clicks = 9",
        (1, campaign, _STAGED_DAY))
    try:
        yield campaign
    finally:
        db.execute_query(
            "DELETE FROM hypeddit_daily_stats WHERE artist_id = %s "
            "AND campaign_name = %s AND date = %s", (1, campaign, _STAGED_DAY))


def test_the_rate_is_the_ratio_of_sums_not_the_average_of_ratios(
        db, staged_second_day) -> None:
    """Les deux formules divergent dès que les jours n'ont pas le même volume.

    C'est le ratio des sommes qui répond à « quel taux ce lien a-t-il obtenu » : la
    moyenne des ratios donne le même poids à un jour de 10 visites et à un jour de
    7 828.
    """
    from src.dashboard.utils.kpi_helpers import clear_kpi_caches
    clear_kpi_caches()

    m = _side(db, 1)
    ctr, visits, clicks = (m["hypeddit_ctr"], m["hypeddit_visits"],
                           m["hypeddit_clicks"])

    rows = db.fetch_query(
        "SELECT SUM(visits), SUM(clicks), "
        "       AVG(clicks::numeric / NULLIF(visits, 0)) * 100 "
        "  FROM v_hypeddit_daily WHERE artist_id = 1 AND campaign_name = %s",
        (staged_second_day,))
    sum_v, sum_c, avg_of_ratios = int(rows[0][0]), int(rows[0][1]), float(rows[0][2])
    ratio_of_sums = sum_c / sum_v * 100

    # La mise en scène doit RÉELLEMENT séparer les deux, sinon l'assertion suivante
    # est satisfaite par n'importe quelle implémentation.
    assert abs(ratio_of_sums - avg_of_ratios) > 5, (
        f"la mise en scène ne discrimine pas : ratio des sommes {ratio_of_sums:.1f} "
        f"contre moyenne des ratios {avg_of_ratios:.1f}")

    assert (visits, clicks) == (sum_v, sum_c), (
        f"les volumes rendus ({visits}, {clicks}) ne sont pas ceux de la campagne "
        f"({sum_v}, {sum_c})")
    assert ctr == pytest.approx(ratio_of_sums, rel=1e-9), (
        f"le taux vaut {ctr:.2f} ; le ratio des sommes vaut {ratio_of_sums:.2f} et "
        f"la moyenne des ratios {avg_of_ratios:.2f}. La valeur rendue suit la "
        "mauvaise formule.")


def test_the_rate_replays_from_the_two_numbers_shown_beside_it(db) -> None:
    """La tuile se vérifie d'un coup d'œil : le taux se rejoue depuis ses volumes."""
    m = _side(db, 1)
    ctr, visits, clicks = (m.get("hypeddit_ctr"), m.get("hypeddit_visits"),
                           m.get("hypeddit_clicks"))
    if ctr is None:
        pytest.skip("aucune campagne Hypeddit liée à la dernière sortie sur cette base")

    assert visits and clicks is not None, (
        "un taux est rendu sans ses volumes : il devient invérifiable")
    assert ctr == pytest.approx(clicks / visits * 100, rel=1e-9), (
        f"le taux ({ctr}) ne vaut pas clics/visites ({clicks}/{visits})")


def test_the_rate_does_not_follow_the_period_filter(db) -> None:
    """Question posée : « qu'a obtenu CETTE sortie », pas « ces trente jours ».

    Bornée au filtre, la tuile serait vide presque toujours : la campagne de
    l'artiste 1 date du 2024-08-30 (mesuré le 2026-09-13). Ce test fige ce choix —
    il rougirait si quelqu'un rebranchait la CTE sur `since`/`until`.
    """
    import datetime as _dt

    whole = _side(db, 1)
    if whole.get("hypeddit_ctr") is None:
        pytest.skip("aucune campagne Hypeddit liée à la dernière sortie sur cette base")
    today = _dt.date.today()
    bounded = _side(db, 1, today - _dt.timedelta(days=30), today)

    assert bounded.get("hypeddit_ctr") == whole.get("hypeddit_ctr"), (
        "le taux Hypeddit change avec le filtre de période : il a été borné, alors "
        "qu'il porte toute l'histoire de la campagne d'une sortie")


def test_an_unmeasured_tenant_gets_none_never_zero(db) -> None:
    """Zéro pour cent et « jamais mesuré » ne sont pas le même fait.

    C'est exactement ce que la colonne `ctr` de la table confond, et la raison pour
    laquelle l'accueil ne la lit pas.
    """
    rows = db.fetch_query(
        "SELECT id FROM saas_artists WHERE id NOT IN "
        "(SELECT DISTINCT artist_id FROM hypeddit_daily_stats) ORDER BY id LIMIT 1")
    if not rows:
        pytest.skip("tous les locataires de cette base ont des données Hypeddit")

    m = _side(db, rows[0][0])
    for key in ("hypeddit_ctr", "hypeddit_visits", "hypeddit_clicks",
                "hypeddit_campaign"):
        assert m.get(key) is None, (
            f"`{key}` vaut {m.get(key)!r} pour un locataire sans la moindre ligne "
            "Hypeddit : une absence est rendue comme une mesure")


_EMPTY_CAMPAIGN = "ZZ garde — campagne sans visite"


@pytest.fixture()
def staged_empty_rival(db):
    """Une SECONDE campagne liée à la même sortie, entièrement à zéro visite.

    ⚠️ CE QU'ELLE MET EN SCÈNE EST UN DÉFAUT RÉEL, vérifié sur la base le
    2026-09-13 : `ORDER BY ctr DESC` place les NULL **en PREMIER** dans Postgres.
    Sans le `HAVING SUM(visits) > 0`, une campagne à zéro visite — donc de taux NULL
    — serait donc choisie DEVANT une campagne à 46 pour cent, et la tuile afficherait
    « — » alors qu'un vrai chiffre existe.

    Sans cette rivale, retirer le `HAVING` laissait le garde au VERT : la seule
    campagne liée du parc a des visites, donc la porte ne changeait rien pour elle.
    Un garde qui ne peut pas rougir ne garde rien.

    Les trois lignes écrites sont retirées dans un `finally`, dans l'ordre inverse
    des dépendances.
    """
    m = _side(db, 1)
    if not m.get("hypeddit_campaign"):
        pytest.skip("aucune campagne Hypeddit liée à la dernière sortie sur cette base")
    key = db.fetch_query(
        "SELECT trr.match_key FROM track_release_reference trr "
        " WHERE trr.artist_id = 1 AND trr.title = %s", (m["release_song"],))
    if not key:
        pytest.skip("la dernière sortie n'a pas de référence canonique")
    match_key = key[0][0]
    db.execute_query(
        "INSERT INTO hypeddit_campaigns (artist_id, campaign_name, is_active) "
        "VALUES (1, %s, TRUE) ON CONFLICT DO NOTHING", (_EMPTY_CAMPAIGN,))
    db.execute_query(
        "INSERT INTO hypeddit_daily_stats (artist_id, campaign_name, date, "
        "visits, clicks) VALUES (1, %s, %s, 0, 0) "
        "ON CONFLICT (artist_id, campaign_name, date) DO NOTHING",
        (_EMPTY_CAMPAIGN, _STAGED_DAY))
    db.execute_query(
        "INSERT INTO track_platform_link (artist_id, match_key, platform, "
        "platform_title, status) VALUES (1, %s, 'hypeddit', %s, 'confirmed') "
        "ON CONFLICT DO NOTHING", (match_key, _EMPTY_CAMPAIGN))
    try:
        yield m["hypeddit_campaign"]
    finally:
        db.execute_query(
            "DELETE FROM track_platform_link WHERE artist_id = 1 "
            "AND platform = 'hypeddit' AND platform_title = %s", (_EMPTY_CAMPAIGN,))
        db.execute_query(
            "DELETE FROM hypeddit_daily_stats WHERE artist_id = 1 "
            "AND campaign_name = %s", (_EMPTY_CAMPAIGN,))
        db.execute_query(
            "DELETE FROM hypeddit_campaigns WHERE artist_id = 1 "
            "AND campaign_name = %s", (_EMPTY_CAMPAIGN,))


def test_a_campaign_with_no_visit_never_wins_the_ranking(
        db, staged_empty_rival) -> None:
    """La campagne vide ne doit ni être choisie, ni effacer celle qui a un chiffre."""
    from src.dashboard.utils.kpi_helpers import clear_kpi_caches
    clear_kpi_caches()

    m = _side(db, 1)

    assert m.get("hypeddit_campaign") == staged_empty_rival, (
        f"la campagne retenue est {m.get('hypeddit_campaign')!r} alors qu'une "
        f"campagne à ZÉRO visite est liée à la même sortie. `ORDER BY ctr DESC` "
        "classe les NULL en premier : sans `HAVING SUM(visits) > 0`, le vide gagne.")
    assert m.get("hypeddit_ctr") is not None, (
        "le taux est devenu NULL alors qu'une campagne mesurée existe")
    assert m.get("hypeddit_visits"), (
        "les volumes sont vides alors qu'une campagne mesurée existe")


def test_the_campaign_is_resolved_by_the_confirmed_link_not_by_its_name(db) -> None:
    """Le nom ne suffit pas, et la base le prouve : les deux titres diffèrent.

    ⚠️ CE TEST NE SE SAUTE PLUS QUAND LA VALEUR EST ABSENTE. Il le faisait, et une
    mutation remplaçant la jointure par `campaign_name = <titre de la sortie>` le
    laissait VERT — cinq tests sautés, un passé. Un saut n'est pas une preuve ; c'est
    la forme que ce dépôt appelle « un test qui passe au vert en s'esquivant ».

    La prémisse est donc MESURÉE d'abord — existe-t-il un lien confirmé ? — et
    l'assertion qui suit est inconditionnelle.
    """
    linked = db.fetch_query("""
        SELECT l.platform_title
          FROM track_platform_link l
          JOIN track_release_reference trr
            ON trr.artist_id = l.artist_id AND trr.match_key = l.match_key
          JOIN ml_song_predictions p
            ON p.artist_id = l.artist_id AND p.song = trr.title
         WHERE l.artist_id = 1 AND l.platform = 'hypeddit'
           AND l.status = 'confirmed'
           AND p.prediction_date = (SELECT MAX(prediction_date)
                                      FROM ml_song_predictions WHERE artist_id = 1)
           AND p.days_since_release = (SELECT MIN(days_since_release)
                                         FROM ml_song_predictions
                                        WHERE artist_id = 1
                                          AND prediction_date = (
                                              SELECT MAX(prediction_date)
                                                FROM ml_song_predictions
                                               WHERE artist_id = 1))
         LIMIT 1""")
    if not linked:
        pytest.skip("la dernière sortie n'a aucun lien Hypeddit confirmé sur cette base")
    expected = linked[0][0]

    m = _side(db, 1)
    release = m.get("release_song")

    # La mise en scène doit rester DISCRIMINANTE : si un jour les deux noms
    # coïncidaient, ce test ne prouverait plus que le lien est nécessaire.
    assert expected != release, (
        f"le nom de la campagne ({expected!r}) est identique à celui de la sortie "
        f"({release!r}) : ce test ne discrimine plus, il faut le remettre en scène")

    assert m.get("hypeddit_campaign") == expected, (
        f"la campagne retenue est {m.get('hypeddit_campaign')!r} au lieu de "
        f"{expected!r}. Le rapprochement ne passe plus par le lien confirmé — une "
        "égalité de noms ne trouve RIEN ici, la casse et le suffixe diffèrent.")
