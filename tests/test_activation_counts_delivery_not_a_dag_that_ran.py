"""Un artiste n'est « activé » que si une plateforme lui a LIVRÉ une ligne.

Type: Test
Uses: live Postgres (spotify_etl), src.utils.activation
Depends on: etl_run_log, saas_artists
Persists in: nothing — tout est écrit dans une transaction annulée

⚠️ CE GARDE EST NÉ SUR UNE MESURE DE PRODUCTION — 2026-09-22 (R149).

Sept locataires en production, et **quatre n'avaient jamais reçu une seule ligne**.
Leur `etl_run_log` ne portait pourtant aucun échec : il portait `skipped`, jusqu'à
quarante-neuf fois pour un même artiste. Le garde d'identité les saute parce qu'ils
n'ont déclaré aucun identifiant de plateforme — état correct — et `alert_monitor`
énonce explicitement que « `skipped` is deliberately NOT a finding ».

Le piège que ce fichier existe pour fermer est plus fin que `skipped`. L'artiste 13
portait **trente exécutions `success` sur SoundCloud, toutes à zéro ligne**. Une
définition d'activation fondée sur `status = 'success'` seul l'aurait compté comme
activé — et aurait annoncé un taux d'activation flatteur sur un compte qui regarde
un écran vide depuis quarante et un jours.

Classe : `a-metric-that-measures-the-machine-instead-of-the-delivery`.

Ce que ce garde couvre : les DEUX moitiés du prédicat de livraison, chacune par une
mutation qui l'incarne, et le fait que la liste des dormants et le compteur soient
d'accord. Ce qu'il NE couvre PAS : la fenêtre de trente jours (un choix, pas une
vérité), le seuil d'une seule plateforme, et toute autre métrique de l'app qui
compterait des exécutions plutôt que des livraisons — la même faute ailleurs
passerait sous ce test sans le faire rougir.
"""
from __future__ import annotations

import pytest

from src.utils.activation import activation_sql, dormant_tenants_sql
from tests.db_gate import db_ready as _db_ready

pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="No provisioned Postgres on 127.0.0.1:5433 — ce garde mesure du SQL réel",
)

# Des identifiants hors de portée de toute donnée réelle.
_A_LIVRE, _A_VIDE, _A_SKIP = 990001, 990002, 990003


@pytest.fixture
def bac():
    """Trois locataires synthétiques, écrits puis ANNULÉS.

    La transaction est explicite parce que `PostgresHandler` vit en `autocommit`.
    Un garde qui laisse des lignes derrière lui fausse la mesure suivante — et
    celle-ci est une mesure de production.
    """
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    conn = db.conn
    conn.autocommit = False
    cur = conn.cursor()
    try:
        for aid, nom in ((_A_LIVRE, "zz-livre"), (_A_VIDE, "zz-vide"),
                         (_A_SKIP, "zz-skip")):
            cur.execute(
                "INSERT INTO saas_artists (id, name, slug, active, tier) "
                "VALUES (%s, %s, %s, TRUE, 'free') ON CONFLICT (id) DO NOTHING",
                (aid, nom, nom),
            )
        lignes = [
            # celui-ci a reçu quelque chose — le seul activé
            (_A_LIVRE, "spotify", "success", 42),
            # `success` à ZÉRO ligne : le cas de l'artiste 13 en production
            (_A_VIDE, "soundcloud", "success", 0),
            # jamais connecté : le cas des artistes 11, 17 et 18
            (_A_SKIP, "spotify", "skipped", 0),
        ]
        for aid, plat, statut, n in lignes:
            cur.execute(
                "INSERT INTO etl_run_log (dag_id, artist_id, platform, status, "
                "rows_inserted, started_at, created_at) "
                "VALUES (%s, %s, %s, %s, %s, NOW(), NOW())",
                (f"test_{plat}", aid, plat, statut, n),
            )
        yield cur
    finally:
        conn.rollback()
        conn.autocommit = True
        db.close()


def _etat(cur) -> tuple[set[int], set[int]]:
    """(les activés, les dormants) parmi nos trois locataires synthétiques."""
    cur.execute(dormant_tenants_sql())
    dormants = {int(r[0]) for r in cur.fetchall()}
    nos = {_A_LIVRE, _A_VIDE, _A_SKIP}
    return nos - dormants, dormants & nos


def test_only_the_tenant_that_received_rows_is_activated(bac):
    actives, dormants = _etat(bac)
    assert actives == {_A_LIVRE}, f"activés inattendus : {actives}"
    assert dormants == {_A_VIDE, _A_SKIP}


def test_a_success_with_zero_rows_does_not_activate(bac):
    """Le défaut EXACT qu'on a vu en production — trente `success`, zéro ligne."""
    _actives, dormants = _etat(bac)
    assert _A_VIDE in dormants, (
        "un `success` à zéro ligne compte comme une activation : la métrique mesure "
        "la machine, pas ce que l'artiste reçoit"
    )


def test_rows_delivered_under_a_failed_status_do_not_activate(bac):
    """L'autre moitié du prédicat, et elle se mute dans l'autre sens.

    Sans ce cas, un prédicat réduit à `rows_inserted > 0` passerait les deux tests
    précédents. On fait donc livrer des lignes à un locataire dont l'exécution a
    ÉCHOUÉ : un lot partiel écrit puis annulé n'est pas une livraison.
    """
    bac.execute(
        "INSERT INTO etl_run_log (dag_id, artist_id, platform, status, "
        "rows_inserted, started_at, created_at) "
        "VALUES ('t', %s, 'youtube', 'failed', 99, NOW(), NOW())",
        (_A_SKIP,),
    )
    _actives, dormants = _etat(bac)
    assert _A_SKIP in dormants, (
        "des lignes comptées sous un statut d'échec activent le compte"
    )


def test_the_counter_and_the_list_agree(bac):
    """Deux surfaces, une définition — le compteur ne peut pas contredire la liste."""
    bac.execute(activation_sql())
    actives_n, total_n = bac.fetchone()
    bac.execute(dormant_tenants_sql())
    dormants_n = len(bac.fetchall())
    assert int(total_n) - int(actives_n) == dormants_n, (
        f"le compteur dit {int(total_n) - int(actives_n)} dormants, "
        f"la liste en nomme {dormants_n}"
    )


def test_an_old_delivery_does_not_activate_today(bac):
    """La fenêtre mord : livrer il y a six mois n'active personne aujourd'hui."""
    bac.execute(
        "INSERT INTO etl_run_log (dag_id, artist_id, platform, status, "
        "rows_inserted, started_at, created_at) "
        "VALUES ('t', %s, 'meta', 'success', 500, "
        "NOW() - INTERVAL '180 days', NOW() - INTERVAL '180 days')",
        (_A_VIDE,),
    )
    _actives, dormants = _etat(bac)
    assert _A_VIDE in dormants, "une livraison hors fenêtre active encore le compte"
