"""Le balayeur de locataire raisonne sur le TYPE d'une colonne, jamais sur son nom.

Type: Test
Uses: importlib
Depends on: .claude/scripts/audit_tenant_writes.py, init_db.sql, migrations/
Persists in: nothing

`.claude/rules/python.md` écrit la règle ET nomme son garde :

    « `artist_id` n'est pas toujours le locataire : sur `artists`, `artist_history`
      et `tracks`, c'est l'identifiant Spotify (VARCHAR) — le locataire y est
      `saas_artist_id` (INTEGER). On raisonne sur le TYPE, jamais sur le nom.
      Garde : python3 .claude/scripts/audit_tenant_writes.py »

Mesuré le 2026-09-17 : **le garde nommé faisait exactement l'inverse.**
`if keys & {"artist_id", "saas_artist_id"}` — n'importe laquelle des deux suffisait.
Conséquences, toutes exécutées avant correctif :

  · `artists`, `tracks` et `artist_history` comptées parmi ses **83 tables
    scopées-locataire** à cause du NOM de leur colonne, alors que deux d'entre elles
    n'ont aucun locataire ;
  · sur `tracks`, une écriture portant le seul `artist_id` Spotify serait passée au
    VERT **sans propriétaire** — le défaut exact que l'outil existe pour attraper.

⚠️ Aucune écriture réelle n'en profitait (`spotify_api_daily.py:363` pose bien
`saas_artist_id`), donc rien ne rougissait. C'est la forme qui survit le plus
longtemps : un garde vert sur ce qu'il prétend garder.

Mutation record — 2026-09-17, trois mutations, trois vues ROUGES (3, 1 et 3 échecs) :
  1. `tables[table] = col` sans le contrôle `_VARCHAR`   → `artists` redevient scopée.
  2. `if tenant_col in keys` → `if keys & _TENANT_KEYS`  → `tracks` accepte l'id Spotify.
  3. `_VARCHAR` rendu introuvable (motif vide)           → les trois tables reviennent.

⚠️ La mutation 2 n'était d'abord couverte que par un test qui lisait le SOURCE de
l'outil et y cherchait des sous-chaînes. `tests/test_a_guard_reads_structure_not_text.py`
l'a REFUSÉE, et il avait raison : un garde textuel rougit sur un commentaire et reste
vert sur une réécriture équivalente. Remplacé par un test qui donne à l'outil
l'écriture fautive — et son jumeau correct, pour qu'un faux positif rougisse aussi.

---
rex: []
---
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TOOL = _ROOT / ".claude" / "scripts" / "audit_tenant_writes.py"


def _tool():
    spec = importlib.util.spec_from_file_location("_audit_tenant_writes", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Les trois tables que la règle NOMME, avec ce que le schéma déclare réellement.
# `tracks` a un `saas_artist_id INTEGER` (init_db.sql) ; les deux autres n'ont que
# l'identifiant Spotify, donc elles ne sont scopées par personne.
_SPOTIFY_KEYED = {
    "tracks": "saas_artist_id",
    "artists": None,
    "artist_history": None,
}


def test_the_tool_still_finds_tenant_tables() -> None:
    """Anti-vacuité : un périmètre vide passerait tous les tests suivants."""
    tables = _tool().tenant_scoped_tables()
    assert len(tables) > 50, (
        f"seulement {len(tables)} tables scopées-locataire — le balayeur ne voit plus "
        "son sujet, et un périmètre vide rend vert tout ce qui suit")


@pytest.mark.parametrize("table,expected", sorted(_SPOTIFY_KEYED.items()))
def test_a_varchar_artist_id_is_not_a_tenant(table: str, expected: str | None) -> None:
    """Sur les trois tables que la règle nomme, c'est le TYPE qui décide."""
    tables = _tool().tenant_scoped_tables()
    got = tables.get(table)
    if expected is None:
        assert got is None, (
            f"`{table}` est comptée scopée-locataire sur `{got}`, mais son `artist_id` "
            "est l'identifiant Spotify (VARCHAR) et elle n'a pas de `saas_artist_id` : "
            "c'est une table de référence globale. La compter gonfle le périmètre et "
            "fait croire à une couverture qui n'existe pas.")
    else:
        assert got == expected, (
            f"`{table}` doit exiger `{expected}` (INTEGER), pas `{got}`. Accepter "
            "`artist_id` ici laisse passer une écriture SANS propriétaire.")


def test_the_type_is_what_decides_not_the_name() -> None:
    """La propriété générale : aucune table ne s'appuie sur un `artist_id` VARCHAR."""
    import re

    module = _tool()
    tables = module.tenant_scoped_tables()
    ddl = (_ROOT / "init_db.sql").read_text(encoding="utf-8")
    fautives = []
    for table, col in tables.items():
        if col != "artist_id":
            continue
        m = re.search(
            rf"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+{table}\s*\((.*?)\n\s*\);",
            ddl, re.S | re.I)
        if not m:
            continue
        decl = re.search(r"^\s*artist_id\s+([^,\n]*)", m.group(1), re.M | re.I)
        if decl and re.search(r"VARCHAR|TEXT|CHAR", decl.group(1), re.I):
            fautives.append(f"{table} (artist_id {decl.group(1).strip()})")
    assert not fautives, (
        "des tables sont scopées sur un `artist_id` NON ENTIER — donc sur un "
        f"identifiant de plateforme, pas sur un locataire : {fautives}")


def test_a_write_to_tracks_carrying_only_the_spotify_id_is_flagged(tmp_path) -> None:
    """Le COMPORTEMENT, pas le texte du source : on lui donne l'écriture fautive.

    ⚠️ Ce test lisait d'abord le SOURCE de l'outil et y cherchait des sous-chaînes.
    `tests/test_a_guard_reads_structure_not_text.py` l'a refusé le 2026-09-17, et il
    avait raison : un garde qui compare du texte rougit sur un commentaire et reste
    vert sur une réécriture équivalente. La question est « l'outil refuse-t-il cette
    écriture ? », et elle se pose en la lui donnant.
    """
    module = _tool()
    tables = module.tenant_scoped_tables()
    assert tables.get("tracks") == "saas_artist_id", "prémisse : `tracks` est scopée par saas_artist_id"

    fautif = tmp_path / "ecriture_fautive.py"
    fautif.write_text(
        "def go(db):\n"
        "    db.upsert_many(table='tracks', data=[{'track_id': 'x', 'artist_id': 'spotify-id'}],\n"
        "                   conflict_columns=['track_id'], update_columns=['track_id'])\n",
        encoding="utf-8")
    verdicts = module.scan_file(fautif, tables)
    assert any(v[0] == "MISSING" for v in verdicts), (
        "une écriture sur `tracks` portant le SEUL `artist_id` Spotify n'est pas "
        f"signalée : {verdicts}. C'est une ligne sans propriétaire, et c'est le "
        "défaut exact que cet outil existe pour attraper.")

    correct = tmp_path / "ecriture_correcte.py"
    correct.write_text(
        "def go(db):\n"
        "    db.upsert_many(table='tracks',\n"
        "                   data=[{'track_id': 'x', 'saas_artist_id': 12}],\n"
        "                   conflict_columns=['track_id'], update_columns=['track_id'])\n",
        encoding="utf-8")
    verdicts = module.scan_file(correct, tables)
    assert not [v for v in verdicts if v[0] == "MISSING"], (
        f"faux positif sur l'écriture CORRECTE : {verdicts}")
