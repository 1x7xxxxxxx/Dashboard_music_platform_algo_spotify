"""Une table inscrite au registre des dimensions ne porte aucune quantité additive.

Type: Test
Uses: psycopg2, a live Postgres
Depends on: tools/dev/gold_coverage.py (`_DIMENSION_TABLES`)
Persists in: nothing

Pourquoi ce registre existe (R108, tranché le 2026-09-14)
----------------------------------------------------------
Trois migrations d'affilée — 116, 120 et la sonde de fraîcheur — ont rendu VISIBLES
des lectures anciennes, simplement en donnant une vue or à une table qu'elles
joignaient. À chaque fois le geste était le même : déclarer site par site.
`saas_artists` est passée de 0 à 4 déclarations en UNE migration, et rien n'arrêtait
la série.

Le registre déclare la TABLE une fois, sur un critère qui ne se discute pas : **cette
table porte-t-elle une quantité additive ?** Une table qui n'en porte aucune ne peut
pas héberger une règle métier recopiée — il n'y a rien à sommer.

Pourquoi ce test lit la BASE
-----------------------------
Sans lui, le registre serait une liste de CONFIANCE : on y inscrit une table, et
personne ne revérifie le jour où elle gagne une colonne. C'est exactement la forme
qu'`an-exemption-that-outlives-what-it-exempted` décrit. Ici l'exemption est une
ASSERTION : la table gagne un `spend`, un `streams` ou un `count` — la CI rougit.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_DB_HOST, _DB_PORT = "127.0.0.1", 5433

# Les types qui peuvent porter une quantité. Un `text` ou une `date` ne s'additionne
# pas ; un `boolean` non plus.
_NUMERIC = {"integer", "bigint", "smallint", "numeric", "real", "double precision"}

# Ce qui est numérique SANS être une quantité additive. La liste est courte et
# explicite : tout le reste doit être justifié en l'ajoutant ici, à la main.
_NOT_A_QUANTITY = {
    "id", "artist_id", "saas_artist_id", "user_id", "track_id", "campaign_id",
    "adset_id", "ad_id", "account_id", "parent_id",
    # Un score par ligne : il qualifie CETTE ligne, il ne s'additionne pas.
    "confidence", "popularity",
    # Une propriété INTRINSÈQUE d'un titre, pas une mesure d'activité. Sommer des
    # durées répond à une question que ce produit ne pose pas — vérifié le
    # 2026-09-14 : aucun SUM ni AVG sur cette colonne dans `src/`. Le jour où une
    # figure sommerait des durées, ce n'est pas cette liste qu'il faut élargir,
    # c'est `tracks` qui cesse d'être une dimension.
    "duration_ms",
    # `plan_id` désigne un plan ; le PRIX de ce plan vit dans la table des plans.
    "plan_id",
    # Des paramètres de facturation par compte, pas des mesures.
    "referral_free_months", "first_month_discount_pct",
    # Un COMPTEUR D'INVALIDATION (migration 123), pas une mesure d'activité. Sa seule
    # opération est `+ 1` et sa seule lecture est une COMPARAISON à la valeur qu'une
    # instance avait vue. Le sommer sur deux locataires répondrait à la question
    # « combien de collectes en tout ? », à laquelle il ne sait pas répondre : une
    # écriture qui n'invalide rien ne l'incrémente pas, et une purge locale non plus.
    # Le jour où une figure voudrait compter les collectes, la source est
    # `etl_run_log`, pas ce compteur.
    "cache_epoch",
}


def _dsn() -> dict | None:
    """Les mots-clés de connexion — par la porte canonique."""
    # ⚠️ LA PORTE CANONIQUE, PAS UNE COPIE — 2026-09-22.
    #
    # Ce bloc construisait son DSN à la main et ne lisait que l'environnement. Sur
    # un poste dont le mot de passe vit dans `config/config.yaml`, la socket
    # s'ouvrait et l'authentification échouait : le skip devenait ERREUR dès qu'une
    # base tournait. Vingt tests rouges d'un coup, aucun lié au changement en cours.
    # `tests/db_gate.dsn()` passe par `src.utils.pg_connect.resolve_kwargs`, qui
    # connaît les trois sources. Classe :
    # `a-second-door-that-knows-fewer-sources-than-the-first`.
    from tests.db_gate import dsn

    return dsn()


_CONN = _dsn()


def _gc():
    """L'import passe par `sys.path`, pas par un chemin littéral.

    Un `spec_from_file_location` n'enregistre pas le module dans `sys.modules`, et
    `@dataclass` y cherche son propre module pour résoudre ses annotations : le
    chargement lève `AttributeError: 'NoneType' object has no attribute '__dict__'`.
    C'est le même import que `test_the_gold_coverage_only_improves`.
    """
    sys.path.insert(0, str(ROOT / "tools" / "dev"))
    import gold_coverage
    return gold_coverage


def _registry() -> dict[str, str]:
    return _gc()._DIMENSION_TABLES


def test_the_registry_is_not_empty():
    """Un registre vide passerait silencieusement tous les tests ci-dessous."""
    assert len(_registry()) >= 3


def test_every_registered_table_names_its_reason():
    for table, why in _registry().items():
        assert len(why) > 40, f"{table} : la raison est trop courte pour être un critère"


@pytest.mark.skipif(_CONN is None,
                    reason=f"No Postgres on {_DB_HOST}:{_DB_PORT} — le critère lit le schéma")
@pytest.mark.parametrize("table", sorted(_registry()))
def test_a_registered_table_carries_no_additive_quantity(table):
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s "
                "ORDER BY ordinal_position", (table,))
            cols = cur.fetchall()
    finally:
        conn.close()
    assert cols, f"{table} n'existe pas — une exemption survit à ce qu'elle exemptait"
    offenders = [c for c, t in cols
                 if t in _NUMERIC and c not in _NOT_A_QUANTITY]
    assert not offenders, (
        f"`{table}` porte {offenders} — des colonnes numériques qui ne sont pas "
        f"déclarées « pas une quantité ». Soit la table a cessé d'être une dimension "
        f"et sort du registre, soit ces colonnes rejoignent _NOT_A_QUANTITY avec la "
        f"raison qui le justifie. Le registre est une assertion, pas une liste de "
        f"confiance.")


@pytest.mark.skipif(_CONN is None, reason="le critère lit le schéma")
def test_the_criterion_would_reject_a_fact_table():
    """Non-vacuité : le critère doit REFUSER une table de fait.

    Sans ça, un `_NUMERIC` vide ou un `_NOT_A_QUANTITY` trop large rendrait chaque
    test ci-dessus vert sur n'importe quoi.
    """
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 's4a_song_timeline'")
            cols = cur.fetchall()
    finally:
        conn.close()
    offenders = [c for c, t in cols if t in _NUMERIC and c not in _NOT_A_QUANTITY]
    assert offenders, (
        "`s4a_song_timeline` porte `streams` : le critère devrait la REFUSER comme "
        "dimension. S'il ne la refuse pas, il ne refuse rien.")


def test_no_registered_table_is_also_declared_site_by_site():
    """Une table du registre n'a plus besoin d'une déclaration par site."""
    mod = _gc()
    both = {t for _rel, t in mod._DECLARED_RAW_AGGREGATES} & set(mod._DIMENSION_TABLES)
    assert not both, (
        f"{sorted(both)} sont déclarées DEUX fois — par la table et par le site. "
        f"La déclaration de site est morte : elle survivra à ce qu'elle exemptait.")
