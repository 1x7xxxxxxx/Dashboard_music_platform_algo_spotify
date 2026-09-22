"""Le €/écoute d'un titre, et l'aveu quand c'est celui de l'artiste.

Type: Test
Uses: src.dashboard.utils.artist_cashflow.track_stream_rate, live Postgres
Depends on: imusician_sales_detail, src.utils.track_matching.canonical_song_sql
Persists in: nothing — tout est écrit dans une transaction annulée

⚠️ DEUX FAITS MESURÉS EN PRODUCTION LE 2026-09-22 justifient cette fonction.

**Le taux varie d'un facteur 10,5 entre les titres du même artiste** — de 0,000387
à 0,004049 €/écoute sur ceux qui dépassent 500 écoutes. Appliquer le taux moyen
d'artiste à tous les titres écraserait exactement l'écart que la page cherche à
montrer.

**La normalisation quadruple la couverture** : sans elle, **1 titre sur 11** se
rattache au distributeur ; avec, **4 sur 11**. `song` vient de `s4a_song_timeline`,
dérivé d'un nom de fichier où Spotify for Artists remplace `< > : " / \\ | ? *` par
`_` ; `track_title` vient du CSV du distributeur et porte les vrais caractères.
« Qui a bu le crachoir du saloon ? » contre « … saloon _ » est le cas d'école.

Et les sept titres qui ne se rattachent pas retombent sur le taux d'artiste. C'est
légitime — mais présenter cet héritage comme une mesure du titre serait une valeur
inventée portant le nom d'un relevé. D'où le champ `source`, que l'écran DOIT lire.

Ce que ce garde NE couvre PAS
------------------------------
(1) Il ne vérifie pas que l'écran affiche bien `source` — c'est une propriété de
rendu. (2) Il ne couvre pas les autres jointures titre du dépôt : le détecteur
automatique de `test_a_song_join_normalises_both_sides.py` ne cherche que
`track_name = %s`, et cette jointure-ci porte sur `track_title`. (3) Il ne juge pas
si le taux du distributeur est le bon taux — la SACEM paie en plus, sur une assiette
différente.
"""
from __future__ import annotations

import pytest

from src.dashboard.utils.artist_cashflow import track_stream_rate
from tests.db_gate import db_ready as _db_ready

pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="No provisioned Postgres on 127.0.0.1:5433 — ce garde mesure du SQL réel",
)

_ARTISTE = 990101
# Le titre porte un « ? » côté distributeur et un « _ » côté S4A — le cas qui
# rendait la jointure muette.
_TITRE_S4A = "Qui a bu le crachoir du saloon _"
_TITRE_DISTRIB = "Qui a bu le crachoir du saloon ?"
_TITRE_SANS_RELEVE = "Un titre que le distributeur ne connaît pas"


@pytest.fixture
def bac():
    """Un artiste synthétique et deux titres, écrits puis ANNULÉS."""
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    conn = db.conn
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO saas_artists (id, name, slug, active, tier) "
            "VALUES (%s, 'zz-taux', 'zz-taux', TRUE, 'free') "
            "ON CONFLICT (id) DO NOTHING", (_ARTISTE,))
        # Le titre rattachable : 1 000 écoutes pour 4 € → 0,004 €/écoute.
        cur.execute(
            "INSERT INTO imusician_sales_detail (artist_id, track_title, quantity, "
            "revenue_eur, sales_year, sales_month, statement_year, statement_month) "
            "VALUES (%s, %s, %s, %s, 2026, 9, 2026, 9)",
            (_ARTISTE, _TITRE_DISTRIB, 1000, 4.0))
        # Un second titre, bien moins payé : 1 000 écoutes pour 0,50 €.
        # Il tire le taux d'ARTISTE vers le bas — c'est lui qui rend le repli
        # distinguable du taux du titre.
        cur.execute(
            "INSERT INTO imusician_sales_detail (artist_id, track_title, quantity, "
            "revenue_eur, sales_year, sales_month, statement_year, statement_month) "
            "VALUES (%s, %s, %s, %s, 2026, 9, 2026, 9)",
            (_ARTISTE, "zz-autre-titre", 1000, 0.5))
        yield db
    finally:
        conn.rollback()
        conn.autocommit = True
        db.close()


def test_a_matching_track_gets_its_own_rate(bac):
    r = track_stream_rate(bac, _ARTISTE, _TITRE_S4A)
    assert r is not None, "aucun taux rendu alors que le relevé existe"
    assert r["source"] == "track", f"source={r['source']!r} — le repli a été pris"
    assert r["eur_par_stream"] == pytest.approx(0.004)


def test_the_normalisation_is_what_makes_it_match(bac):
    """Le cas d'école, isolé : « ? » d'un côté, « _ » de l'autre.

    Sans la normalisation des deux côtés, cette recherche ne rend rien et le titre
    retombe sur le taux d'artiste — un repli qui passerait pour « pas de relevé ».
    """
    normalise = track_stream_rate(bac, _ARTISTE, _TITRE_S4A)
    exact = track_stream_rate(bac, _ARTISTE, _TITRE_DISTRIB)
    assert normalise["source"] == "track"
    assert exact["source"] == "track", (
        "la forme exacte ne se rattache plus — la normalisation a cassé le cas simple"
    )
    assert normalise["eur_par_stream"] == pytest.approx(exact["eur_par_stream"])


def test_a_track_with_no_sales_falls_back_and_admits_it(bac):
    """Le repli est explicite, jamais silencieux."""
    r = track_stream_rate(bac, _ARTISTE, _TITRE_SANS_RELEVE)
    assert r is not None, "le repli sur le taux d'artiste n'a pas eu lieu"
    assert r["source"] == "artist", (
        f"source={r['source']!r} : un titre sans relevé est présenté comme mesuré"
    )
    # 2 000 écoutes pour 4,50 € tous titres confondus
    assert r["eur_par_stream"] == pytest.approx(4.5 / 2000)


def test_the_two_rates_really_differ(bac):
    """Anti-vacuité : si le repli valait le taux du titre, rien ne serait testé."""
    titre = track_stream_rate(bac, _ARTISTE, _TITRE_S4A)["eur_par_stream"]
    repli = track_stream_rate(bac, _ARTISTE, _TITRE_SANS_RELEVE)["eur_par_stream"]
    assert titre != pytest.approx(repli), (
        "le taux du titre et le repli d'artiste sont égaux — le bac à sable ne "
        "distingue pas les deux chemins, donc les tests au-dessus ne prouvent rien"
    )


def test_an_artist_with_nothing_measurable_gets_none(bac):
    """`None`, jamais un zéro : une absence de relevé n'est pas un revenu nul."""
    assert track_stream_rate(bac, 990102, _TITRE_S4A) is None
