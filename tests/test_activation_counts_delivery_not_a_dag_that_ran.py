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

⚠️ SON HARNAIS NOURRISSAIT LA MAUVAISE PORTE — corrigé le 2026-09-22 au soir
------------------------------------------------------------------------------
Écrit le matin, ce fichier écrivait ses trois locataires synthétiques dans
`etl_run_log`, parce que c'est là que `activation_sql` lisait. L'après-midi a mesuré
que ce journal MENT, et dans les deux sens :

    (12, youtube)   32 `success`, rows_inserted=0 partout  →  95 LIGNES, du JOUR
    (13, soundcloud) 31 `success`, rows_inserted=0 partout →  0 ligne

`rows_inserted = 0` dit « cette exécution n'a rien inséré » — vrai d'un upsert
idempotent qui ne trouve rien de neuf — jamais « cette plateforme ne livre pas ». Sur
les deux paires à zéro partout, **une sur deux est un mensonge** : YouTube alimente
Benken tous les jours. `activation_sql` lit donc désormais les TABLES DE DONNÉES.

Un harnais qui nourrit l'ancienne source de vérité ne teste plus rien : ce fichier est
sorti ROUGE de la correction, en annonçant `set()` là où il attendait un activé, et
c'était le bon comportement. Il écrit maintenant dans les tables de données, ce qui le
rend PLUS fort qu'avant : le cas `_A_VIDE` porte désormais un `success` à **42 lignes**
dans le journal et **rien** en base — la forme la plus dure du défaut d'origine — et un
cas neuf reproduit Benken, de la donnée fraîche sans aucun log favorable.

Ce que ce garde couvre : les deux sens de la divergence journal/donnée, chacun par un
locataire qui l'incarne, la fenêtre, et l'accord entre le compteur et la liste des
dormants. Ce qu'il NE couvre PAS : la JUSTESSE de la fenêtre de trente jours (un choix,
pas une vérité), le seuil d'une seule plateforme, et toute autre métrique de l'app qui
compterait des exécutions plutôt que des livraisons — la même faute ailleurs passerait
sous ce test sans le faire rougir.
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
        # ── LA DONNÉE, qui est la seule source de vérité de l'activation ──────
        #
        # `_A_LIVRE` reçoit une ligne en base ET un journal DÉFAVORABLE : `success` à
        # zéro ligne, exactement la forme de (12, youtube) en production. C'est le cas
        # que l'ancien prédicat comptait comme dormant alors que l'artiste voit des
        # données fraîches chaque jour.
        cur.execute(
            "INSERT INTO youtube_channel_history (channel_id, subscriber_count, "
            "video_count, view_count, collected_at, artist_id) "
            "VALUES ('zz-chan', 10, 1, 100, NOW(), %s)", (_A_LIVRE,))

        # ── LE JOURNAL, qui ne doit plus rien décider ─────────────────────────
        lignes = [
            # Journal DÉFAVORABLE sur un compte qui a de la donnée : le cas Benken.
            (_A_LIVRE, "youtube", "success", 0),
            # Journal FAVORABLE — 42 lignes annoncées — et RIEN en base. La forme la
            # plus dure du défaut d'origine : avant, ce compte était « activé ».
            (_A_VIDE, "soundcloud", "success", 42),
            # Jamais connecté : le cas des artistes 11, 13 et 17.
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


def test_only_the_tenant_whose_table_holds_a_row_is_activated(bac):
    """La propriété, en un coup d'œil : la DONNÉE décide, le journal ne décide rien."""
    actives, dormants = _etat(bac)
    assert actives == {_A_LIVRE}, f"activés inattendus : {actives}"
    assert dormants == {_A_VIDE, _A_SKIP}


def test_data_in_the_table_activates_even_when_the_log_says_zero(bac):
    """LE CAS BENKEN, reproduit — et celui que l'ancien prédicat ratait.

    `_A_LIVRE` porte une ligne fraîche dans `youtube_channel_history` ET un journal
    qui annonce `success` à **zéro ligne**. En production, (12, youtube) porte
    exactement cette forme : 32 exécutions à zéro, 95 lignes en base, la plus récente
    du jour même. Un upsert idempotent qui ne trouve rien de neuf n'insère rien et
    n'efface rien.
    """
    actives, _dormants = _etat(bac)
    assert _A_LIVRE in actives, (
        "un locataire dont la table de données porte une ligne fraîche est compté "
        "DORMANT parce que son journal annonce zéro insertion. C'est le défaut mesuré "
        "en production le 2026-09-22 : `rows_inserted` dit ce qu'une EXÉCUTION a "
        "inséré, jamais ce que la base CONTIENT."
    )


def test_a_log_that_claims_rows_does_not_activate_without_the_data(bac):
    """L'AUTRE SENS, et il est plus dur que la version d'origine.

    `_A_VIDE` porte un `success` annonçant **42 lignes** et RIEN en base. La version
    de ce test écrite le matin utilisait un `success` à ZÉRO ligne — un prédicat
    réduit à `rows_inserted > 0` la passait. Ici aucun prédicat sur le journal ne
    peut la passer : seule une lecture de la table y arrive.
    """
    _actives, dormants = _etat(bac)
    assert _A_VIDE in dormants, (
        "un journal qui annonce 42 lignes active le compte alors que sa table est "
        "vide : la métrique mesure la machine, pas ce que l'artiste reçoit"
    )


def test_rows_claimed_under_a_failed_status_do_not_activate(bac):
    """Un statut d'échec ne peut pas non plus activer — il n'a plus de voix du tout.

    Le prédicat ne lit plus le statut, donc ce test ne vérifie plus une moitié de
    condition : il vérifie que le journal est SANS EFFET, quel que soit ce qu'il dit.
    C'est plus faible en intention et plus fort en portée.
    """
    bac.execute(
        "INSERT INTO etl_run_log (dag_id, artist_id, platform, status, "
        "rows_inserted, started_at, created_at) "
        "VALUES ('t', %s, 'youtube', 'failed', 99, NOW(), NOW())",
        (_A_SKIP,),
    )
    _actives, dormants = _etat(bac)
    assert _A_SKIP in dormants, (
        "des lignes ANNONCÉES par le journal activent le compte : il ne devrait avoir "
        "aucune voix, quel que soit son statut"
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


def test_an_old_row_does_not_activate_today(bac):
    """La fenêtre mord sur la DONNÉE : une ligne de six mois n'active personne.

    Écrite dans la table, pas dans le journal — sinon ce test ne vérifierait plus que
    l'inertie d'une source que le prédicat ne lit plus.
    """
    bac.execute(
        "INSERT INTO soundcloud_tracks_daily (track_id, artist_id, collected_at) "
        "VALUES ('zz-old', %s, NOW() - INTERVAL '180 days')",
        (_A_VIDE,),
    )
    _actives, dormants = _etat(bac)
    assert _A_VIDE in dormants, (
        "une ligne vieille de six mois active encore le compte : la fenêtre ne mord "
        "plus sur la date de la donnée."
    )


def test_a_fresh_row_in_that_same_table_does_activate(bac):
    """NON-VACUITÉ du test ci-dessus : la fenêtre doit SÉPARER, pas tout refuser.

    Sans lui, un prédicat qui rejetterait `soundcloud_tracks_daily` en entier — table
    mal orthographiée, colonne renommée, branche disparue du registre — passerait le
    test de la fenêtre pour la mauvaise raison.
    """
    bac.execute(
        "INSERT INTO soundcloud_tracks_daily (track_id, artist_id, collected_at) "
        "VALUES ('zz-new', %s, NOW())",
        (_A_VIDE,),
    )
    actives, _dormants = _etat(bac)
    assert _A_VIDE in actives, (
        "une ligne FRAÎCHE dans la même table n'active pas : ce n'est donc pas la "
        "fenêtre qui décide, c'est la branche qui est morte."
    )
