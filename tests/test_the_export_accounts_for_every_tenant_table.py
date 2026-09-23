"""Garde : l'export « toutes tes données » rend compte de CHAQUE table du locataire.

Type: Utility
Uses: pytest, zipfile, src.dashboard.utils.csv_exporter, tests.db_gate
Triggers: pytest
Persists in: nothing — the behavioural case writes in a transaction that is rolled back

Ce qui a été mesuré le 2026-09-23 (R164)
-----------------------------------------
`csv_exporter._TABLES` était une liste tenue à la main : **18 tables de locataire sur
79**, sous une légende qui promettait « tes données uniquement ». Même défaut, même
jour, que la portée de l'effacement RGPD — la classe
`guard-scope-is-a-hand-written-list`. Et une SECONDE liste, `_SOURCE_GROUPS` dans la
vue, décidait quelles tables on pouvait cocher : une table ajoutée à l'une et oubliée
dans l'autre ne sortait jamais.

Le remède n'est pas de tout exporter : `saas_users` porte l'empreinte du mot de passe,
`artist_credentials` des identifiants chiffrés. Chaque table est donc EXPORTÉE ou
EXCLUE AVEC SA RAISON (`_NOT_EXPORTED`) — la forme de
`tests/test_contamination_scope_is_derived.py`.

Ce que ce garde couvre : la partition complète et disjointe des tables du locataire
lues dans le schéma vivant ; une source de case à cocher par table exportée ;
l'isolation (un export ne rend pas la ligne d'un autre locataire, y compris sur
`tracks`, dont le locataire est `saas_artist_id`). Ce qu'il NE couvre PAS : la
JUSTESSE d'une raison d'exclusion (un humain la lit), ni les colonnes sensibles d'une
table exportée — une colonne secrète ajoutée demain à une table de données partirait
dans le ZIP.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from src.dashboard.utils.csv_exporter import (
    SOURCE_GROUPS, _NOT_EXPORTED, _TABLES, export_all, table_names)
from tests.db_gate import db_ready as _db_ready

_needs_db = pytest.mark.skipif(not _db_ready(), reason="No provisioned Postgres on 5433")
_GLOBAL = {"algo_lifecycle_benchmark"}  # reference curves, no tenant column
_TENANT, _OTHER = 990301, 990302


def test_every_exported_table_can_be_ticked_and_only_once() -> None:
    grouped = [tb for tbs in SOURCE_GROUPS.values() for tb in tbs]
    assert len(grouped) == len(set(grouped)), "une table est dans deux groupes"
    assert set(grouped) == set(table_names()), (
        f"exportables sans case : {sorted(set(table_names()) - set(grouped))} ; "
        f"cases sans table : {sorted(set(grouped) - set(table_names()))}")


def test_a_table_is_exported_or_excluded_never_both() -> None:
    both = sorted(set(table_names()) & set(_NOT_EXPORTED))
    assert not both, f"{both} sont à la fois exportées et exclues"
    assert all(reason.strip() for reason in _NOT_EXPORTED.values()), "une exclusion sans raison"


@_needs_db
def test_every_tenant_table_is_exported_or_excluded_with_a_reason() -> None:
    from src.dashboard.views.admin_accounts import _tenant_columns_in_schema
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    try:
        tenant = {tb for tb, _ in _tenant_columns_in_schema(db)} | {"saas_users", "saas_artists"}
    finally:
        db.close()
    assert len(tenant) > 50, f"non-vacuité : {len(tenant)} table(s) de locataire seulement"
    unaccounted = sorted(tenant - set(table_names()) - set(_NOT_EXPORTED))
    assert not unaccounted, (
        f"{unaccounted} portent des données du locataire et ne sont ni exportées ni "
        "exclues avec une raison. Les ajouter à `_TABLES` (et à `SOURCE_GROUPS`), ou à "
        "`_NOT_EXPORTED` en disant pourquoi.")
    exported_global = sorted(set(table_names()) & tenant & _GLOBAL)
    assert not exported_global, f"{exported_global} déclarées globales mais scopées"


def test_every_tenant_query_is_filtered_by_its_tenant() -> None:
    unfiltered = [name for name, sql, params in _TABLES
                  if name not in _GLOBAL and ("= %s" not in sql or params(1) != (1,))]
    assert not unfiltered, f"{unfiltered} : requête d'export sans filtre de locataire"


@pytest.fixture
def db():
    from src.database.postgres_handler import PostgresHandler

    handler = PostgresHandler.from_env_or_config()
    handler.conn.autocommit = False
    try:
        yield handler
    finally:
        handler.conn.rollback()
        handler.conn.autocommit = True


@_needs_db
def test_the_archive_carries_a_new_table_and_nobody_elses_rows(db) -> None:
    cur = db.conn.cursor()
    for aid, slug in ((_TENANT, "zz-export"), (_OTHER, "zz-export-other")):
        cur.execute("INSERT INTO saas_artists (id, name, slug, active, tier) "
                    "VALUES (%s, %s, %s, TRUE, 'free')", (aid, slug, slug))
        cur.execute("INSERT INTO tracks (track_id, track_name, saas_artist_id) "
                    "VALUES (%s, %s, %s)", (f"{slug}-t", f"{slug}-title", aid))

    archive = zipfile.ZipFile(io.BytesIO(export_all(db, _TENANT, ["tracks"]).getvalue()))
    assert "tracks.csv" in archive.namelist(), archive.namelist()
    csv = archive.read("tracks.csv").decode()
    assert "zz-export-title" in csv, "la table ajoutée par R164 ne sort pas dans l'archive"
    assert "zz-export-other-title" not in csv, (
        "l'archive porte la ligne d'un AUTRE locataire : `tracks` filtrée sur "
        "`artist_id` (l'identifiant Spotify) au lieu de `saas_artist_id`.")
