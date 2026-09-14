"""Une retenue ne se retranche que de la base qui l'a produite.

Type: Test
Uses: psycopg2, a live Postgres (vue `v_artist_monthly_revenue_net`, migration 115)
Depends on: migrations/115_gold_revenue_gross_and_net.sql
Persists in: nothing — tout est écrit dans une transaction ANNULÉE

Le défaut gardé, mesuré le 2026-09-14
--------------------------------------
La page Royalties SACEM affichait « ✅ Net estimé » calculé en Python :

    net = gross + charges + tva          →  43,06 − 6,90 − 14,67 = 21,49 €

L'artiste avait reçu **36,49 €** — la somme de ses quatre virements Caisse d'Épargne.
La page se trompait de 15,00 €, soit **41 %**, sur le seul chiffre qu'il pouvait
vérifier lui-même sur son relevé bancaire.

Les 9 lignes `tva` du relevé ne sont pas une population homogène : 8 sont des
`FORFAIT TVA` **positifs** (+0,01 à +0,11), reversés AVEC chaque répartition, et une
est la TVA des frais d'adhésion de 2023 (**−15,00 €**), qui appartient à un bloc se
soldant à zéro — +100,00 versés, −75,00 de frais, −10,00 de part sociale, −15,00 de
TVA — et ne concerne aucune royaltie.

Classe `a-deduction-subtracted-from-the-wrong-base` : le TYPE d'une ligne dit ce
qu'elle est, jamais de quoi elle se retranche.

Pourquoi un relevé de SYNTHÈSE et pas les données réelles
----------------------------------------------------------
Un test adossé au relevé de l'artiste 1 serait vert sur une base vide et muet chez
quiconque n'a pas encore importé de SACEM — la moitié des locataires. Il construit
donc son propre relevé, avec les deux blocs qui font le défaut, dans une transaction
annulée. La règle est vérifiée, pas la donnée d'un locataire.

Pourquoi PAS un invariant permanent net == virements
-----------------------------------------------------
L'égalité n'est vraie qu'une fois tout distribué. Une répartition de janvier attend
son virement d'avril : entre les deux, net ≠ virements, **normalement**. En faire un
invariant de `gold_invariants.py` aurait produit un contrôle rouge en régime normal —
la classe `a-check-that-can-never-pass`, déjà payée ici avec `rclone` appelé depuis un
conteneur qui ne l'avait pas.
"""
from __future__ import annotations

import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _dsn() -> dict | None:
    if os.environ.get("DATABASE_URL"):
        return {"dsn": os.environ["DATABASE_URL"]}
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            pass
    except OSError:
        return None
    return {
        "host": _DB_HOST,
        "port": _DB_PORT,
        "dbname": os.environ.get("DATABASE_NAME", "spotify_etl"),
        "user": os.environ.get("DATABASE_USER", "postgres"),
        "password": os.environ.get("DATABASE_PASSWORD") or os.environ.get("DB_PASSWORD", ""),
    }


_CONN = _dsn()

pytestmark = pytest.mark.skipif(
    _CONN is None,
    reason=f"No Postgres on {_DB_HOST}:{_DB_PORT} — la règle vit dans une vue SQL",
)

# Le relevé de synthèse : le bloc d'adhésion de 2023, puis deux trimestres de
# royalties. Les montants sont ceux du relevé réel, pour que les nombres attendus
# ci-dessous soient reconnaissables par qui a vu le défaut.
_LEDGER = [
    # (mois, libellé, mouvement, type)
    ("2023-01-26", "Adm ARTISTE DE SYNTHESE", 100.00, "other"),
    ("2023-01-26", "Frais d'admission", -75.00, "admission"),
    ("2023-01-26", "Part sociale", -10.00, "admission"),
    ("2023-01-26", "Tva /frais d'admission", -15.00, "tva"),
    ("2024-04-05", "REPARTITION 666", 4.07, "repartition"),
    ("2024-04-05", "CSG DEDUCTIBLE 6.80%", -0.27, "charge"),
    ("2024-04-05", "CRDS 0.50%", -0.02, "charge"),
    ("2024-04-05", "FORFAIT TVA", 0.03, "tva"),
    ("2024-07-05", "REPARTITION 667", 6.87, "repartition"),
    ("2024-07-05", "CSG DEDUCTIBLE 6.80%", -0.46, "charge"),
    ("2024-07-05", "FORFAIT TVA", 0.05, "tva"),
]

_GROSS = 4.07 + 6.87                                   # 10,94 — les répartitions
_DEDUCTIONS = (-0.27 - 0.02 + 0.03) + (-0.46 + 0.05)   # −0,67 — liées à une répartition
_NET = _GROSS + _DEDUCTIONS                            # 10,27
_NAIVE_NET = _GROSS + _DEDUCTIONS - 15.00              # −4,73 — l'ancien calcul


@pytest.fixture()
def seeded():
    """Un locataire jetable et son relevé, dans une transaction ANNULÉE."""
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO saas_artists (name, slug, tier, active) "
                "VALUES ('Net Rule', 'net-rule-fixture', 'free', TRUE) RETURNING id")
            artist_id = cur.fetchone()[0]
            solde = 0.0
            for line_date, libelle, mouvement, line_type in _LEDGER:
                solde += mouvement
                cur.execute(
                    "INSERT INTO sacem_statement (artist_id, line_date, libelle, "
                    "  mouvement_eur, solde_eur, line_type, source) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 'test_fixture')",
                    (artist_id, line_date, libelle, mouvement, round(solde, 2), line_type))
            yield cur, artist_id
    finally:
        conn.rollback()   # rien n'est écrit — la vue est lue DANS la transaction
        conn.close()


def _net_row(cur, artist_id) -> tuple[float, float, float]:
    cur.execute(
        "SELECT COALESCE(SUM(gross_eur), 0), COALESCE(SUM(deductions_eur), 0), "
        "       COALESCE(SUM(net_eur), 0) "
        "FROM v_artist_monthly_revenue_net WHERE artist_id = %s AND source = 'sacem'",
        (artist_id,))
    g, d, n = cur.fetchone()
    return float(g), float(d), float(n)


def test_the_membership_block_does_not_reduce_the_royalties(seeded):
    """Le défaut exact : −15,00 € de TVA d'adhésion retranchés de royalties."""
    cur, artist_id = seeded
    _gross, deductions, net = _net_row(cur, artist_id)
    assert net == pytest.approx(_NET, abs=0.005), (
        f"net = {net:.2f} € au lieu de {_NET:.2f} €. "
        f"L'ancien calcul rendait {_NAIVE_NET:.2f} € en retranchant la TVA du bloc "
        f"d'adhésion de 2023 — une retenue qui ne porte sur aucune royaltie.")
    assert deductions == pytest.approx(_DEDUCTIONS, abs=0.005), (
        f"retenues = {deductions:.2f} € au lieu de {_DEDUCTIONS:.2f} €")


def test_the_gross_ignores_every_line_that_is_not_a_distribution(seeded):
    """Le brut ne bouge pas : c'est la définition de la migration 111, inchangée."""
    cur, artist_id = seeded
    gross, _deductions, _net = _net_row(cur, artist_id)
    assert gross == pytest.approx(_GROSS, abs=0.005), (
        f"brut = {gross:.2f} € au lieu de {_GROSS:.2f} € — une ligne autre que "
        f"`repartition` est entrée dans le brut")


def test_a_month_without_a_distribution_contributes_nothing(seeded):
    """La règle, énoncée au grain où elle s'applique : janvier 2023 rend 0 partout."""
    cur, artist_id = seeded
    cur.execute(
        "SELECT gross_eur, deductions_eur, net_eur FROM v_artist_monthly_revenue_net "
        "WHERE artist_id = %s AND source = 'sacem' AND year = 2023 AND month = 1",
        (artist_id,))
    row = cur.fetchone()
    assert row is not None, "le mois d'adhésion a disparu de la vue au lieu de rendre 0"
    assert [float(v) for v in row] == [0.0, 0.0, 0.0], (
        f"janvier 2023 rend {row} — un mois sans répartition n'a pas de retenue SUR "
        f"des royalties, son bloc se solde ailleurs")


# --- non-vacuité : la fixture porte bien le défaut ------------------------------

def test_the_fixture_actually_contains_the_defective_shape(seeded):
    """Sans la ligne de TVA d'adhésion, ce fichier ne garderait rien."""
    cur, artist_id = seeded
    cur.execute(
        "SELECT COUNT(*) FROM sacem_statement WHERE artist_id = %s "
        "AND line_type = 'tva' AND mouvement_eur < 0", (artist_id,))
    assert cur.fetchone()[0] == 1, (
        "la fixture ne contient plus de TVA négative hors répartition — elle ne "
        "distingue donc plus la bonne règle de l'ancienne")
    assert round(_NAIVE_NET, 2) != round(_NET, 2), (
        "les deux règles rendent le même nombre sur cette fixture : elle ne prouve rien")


def test_the_naive_rule_would_fail_this_test(seeded):
    """Mutation jouée EN SQL : la règle d'avant rend un net négatif sur ce relevé."""
    cur, artist_id = seeded
    cur.execute(
        "SELECT COALESCE(SUM(amount) FILTER (WHERE line_type = 'repartition'), 0) "
        "     + COALESCE(SUM(amount) FILTER (WHERE line_type IN ('charge', 'tva')), 0) "
        "FROM v_sacem_monthly WHERE artist_id = %s", (artist_id,))
    naive = float(cur.fetchone()[0])
    assert naive == pytest.approx(_NAIVE_NET, abs=0.005)
    _gross, _deductions, net = _net_row(cur, artist_id)
    assert net != pytest.approx(naive, abs=0.005), (
        "la vue rend le même nombre que la règle naïve — le correctif n'est pas en "
        "place, ou la migration 115 n'a pas été appliquée")
