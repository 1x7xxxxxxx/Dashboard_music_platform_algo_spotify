"""Un inventaire fait sur les écrivains Python rate ce qu'un DÉCLENCHEUR écrit.

Type: Test
Uses: la base joignable
Depends on: src/utils/telemetry_retention, migrations/128_*.sql
Persists in: nothing

Pourquoi ce garde existe
------------------------
La migration 124 a fait l'inventaire des tables de télémétrie et leur a donné une
rétention déclarée. **Deux y ont échappé, pour deux raisons symétriques** — et c'est la
symétrie qui en fait une classe plutôt qu'un oubli :

  * `data_revisions` : **ni déclarée ni purgée**. Elle est écrite par un DÉCLENCHEUR SQL
    (`log_value_revision()`), jamais par du code applicatif — et l'inventaire a été fait
    sur les écrivains PYTHON. Une table qu'aucun `INSERT` Python ne touche était
    invisible à la question posée.
  * `rate_limit_hits` : **purgée sans être déclarée**. Son commentaire nommait bien son
    purgeur, mais pas dans la forme `RÉTENTION : N jours` que
    `declared_retentions()` lit — donc `undeclared_tables()` ne pouvait pas la juger.

⚠️ **La rétention est DÉRIVÉE du commentaire**, pas documentée par lui :
`telemetry_retention.py:62` lit `RÉTENTION : (\\d+) jours` dans `obj_description()` et
`purge_telemetry` agit dessus. Déclarer CÂBLE la purge. C'est pourquoi le geste est une
migration et non un commentaire de code.

⚠️ Et l'ordre a compté : `undeclared_tables()` a rougi sur ces deux tables entre la
déclaration et l'ajout de leur colonne d'âge. C'est sa raison d'être — une rétention
déclarée sans colonne connue fait échouer la purge LA NUIT VENUE, sur une table que la
migration vient d'annoncer purgée.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.telemetry_retention import _AGE_COLUMN  # noqa: E402

_LES_DEUX = ("data_revisions", "rate_limit_hits")


def _db():
    from src.database.postgres_handler import PostgresHandler
    try:
        return PostgresHandler.from_env_or_config()
    except Exception:                          # noqa: BLE001
        return None


@pytest.mark.parametrize("table", _LES_DEUX)
def test_each_of_the_two_declares_a_retention(table: str) -> None:
    """LE GARDE. La déclaration est ce qui câble la purge."""
    from src.utils.telemetry_retention import declared_retentions
    db = _db()
    if db is None:
        pytest.skip("base injoignable")
    try:
        commentaire = declared_retentions(db).get(table)
    finally:
        db.close()
    assert commentaire, (
        f"`{table}` ne déclare aucune rétention. `purge_telemetry` la dérive du "
        "commentaire de table : sans déclaration, la table n'est pas purgée du tout, et "
        "`undeclared_tables()` ne peut même pas signaler l'absence.")
    assert "RÉTENTION" in commentaire.upper(), (
        f"`{table}` a un commentaire mais pas dans la forme que "
        "`declared_retentions()` lit. C'est exactement le cas de `rate_limit_hits` "
        "avant le 2026-09-20 : purgée, et invisible à son propre contrôle.")


@pytest.mark.parametrize("table", _LES_DEUX)
def test_each_of_the_two_names_its_age_column(table: str) -> None:
    """Une rétention sans colonne d'âge fait échouer la purge LA NUIT VENUE."""
    assert table in _AGE_COLUMN, (
        f"`{table}` déclare une rétention et n'a pas de colonne d'âge dans `_AGE_COLUMN`. "
        "`purge_telemetry` ne saurait pas sur quoi compter les jours — et l'échec "
        "arriverait pendant l'exécution nocturne, pas ici.")


def test_nothing_declares_a_retention_without_its_column() -> None:
    """LE CLIQUET, et il a rougi pendant l'écriture de cette migration.

    Il n'est pas décoratif : entre le `COMMENT ON TABLE` et l'ajout des deux colonnes,
    il a listé les deux tables. C'est le seul moment où ce défaut est visible sans
    attendre la nuit.
    """
    from src.utils.telemetry_retention import undeclared_tables
    db = _db()
    if db is None:
        pytest.skip("base injoignable")
    try:
        manquantes = undeclared_tables(db)
    finally:
        db.close()
    assert not manquantes, (
        f"rétention(s) déclarée(s) sans colonne d'âge : {manquantes}. La purge "
        "échouerait à la prochaine exécution nocturne.")


def test_the_purge_actually_reaches_the_two_tables() -> None:
    """ANTI-VACUITÉ : déclarer ne prouve pas que la purge les ATTEINT.

    Une purge à blanc doit les nommer. Sans ce test, une déclaration correcte et un
    purgeur qui les ignore donneraient exactement le même vert.
    """
    from src.utils.telemetry_retention import purge_telemetry
    db = _db()
    if db is None:
        pytest.skip("base injoignable")
    try:
        resultat = purge_telemetry(db, dry_run=True)
    finally:
        db.close()
    atteintes = set(resultat.get("purged") or {})
    manquantes = [t for t in _LES_DEUX if t not in atteintes]
    assert not manquantes, (
        f"la purge à blanc n'atteint pas {manquantes}. Elles sont déclarées et le "
        "purgeur passe à côté — le pire des deux mondes : un contrôle vert sur une "
        "table qui grossit.")
