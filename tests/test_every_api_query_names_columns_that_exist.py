"""Une requête de l'API nomme des colonnes qui existent — vérifié contre la BASE.

Type: Test
Uses: ast, re, live Postgres (spotify_etl)
Depends on: src/api/**/*.py, information_schema
Persists in: nothing

`api-router-schema-drift` : un routeur SELECT une colonne qu'une migration ultérieure a
renommée, et l'endpoint rend 500 pour tous les locataires. `test_api.py` ne peut pas le
voir — sa base est un `MagicMock`, qui répond à n'importe quelle colonne.

Le filet existant, `tests/test_api_db_smoke.py`, appelle les endpoints avec un jeton
forgé. Balayé le 2026-09-18 : il couvre **7 des 9 routes** déclarées. Les deux qu'il ne
peut pas appeler sont `POST /auth/token` — il forge le jeton au lieu de se connecter,
donc il ne passe jamais par la requête de connexion — et `POST /stripe`, un webhook.

⚠️ La route de connexion lit **onze colonnes de `saas_users`**. Une seule renommée, et
plus personne ne se connecte — une panne strictement pire que celle d'un endpoint de
données, et la seule qu'aucun test ne pouvait voir. Vérifié le 2026-09-18 : les onze
existent. Ce fichier fige ce fait au lieu de le redécouvrir en production.

Le prédicat
-----------
On lit les littéraux SQL de `src/api/`, on garde ceux dont la liste de colonnes est
SANS ambiguïté (pas de `*`, pas d'appel de fonction, pas d'alias, un seul `FROM`), et on
compare chaque nom à `information_schema`. Tout ce qui est ambigu est SAUTÉ — un garde
qui devine produit du bruit, et le bruit apprend à ignorer le rouge.

Ce qu'il ne couvre PAS
----------------------
Les colonnes citées dans un `WHERE`, un `ORDER BY` ou un `JOIN` — seule la projection
est lue. Les requêtes composées à l'exécution. Et le TYPE d'une colonne : elle peut
exister et avoir changé de nature, ce qu'aucune lecture de nom ne verra.

Mutation record — 2026-09-18 : en renommant `token_version` en `token_versionXX` dans
la requête de `src/api/auth.py:75`, ce garde la nomme ; remis, il passe.

---
rex: []
---
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.db_gate import db_ready as _db_ready

_ROOT = Path(__file__).resolve().parents[1]
_API = _ROOT / "src" / "api"

pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="No provisioned Postgres on 127.0.0.1:5433 — a schema check needs the schema",
)

_SELECT = re.compile(r"SELECT\s+(?P<cols>.+?)\s+FROM\s+(?P<table>[a-z_][a-z0-9_]*)",
                     re.I | re.S)
# Insensible à la CASSE, et les noms sont comparés en minuscules : un identifiant
# SQL non cité l'est aussi. Le premier jet exigeait le tout-minuscule, et une
# colonne à casse mixte faisait écarter TOUTE la projection comme ambiguë — le
# garde devenait alors muet sur la requête qu'il est seul à surveiller. Trouvé
# en mutant : renommer `token_version` en `token_versionXX` ne le faisait pas
# rougir sur la colonne, mais disparaître du balayage.
_PLAIN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _unambiguous_projections() -> list[tuple[str, int, str, list[str]]]:
    """(fichier, ligne, table, colonnes) pour chaque projection lisible sans deviner."""
    out = []
    for path in sorted(_API.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:                                  # pragma: no cover
            continue
        textes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                textes.append((node.lineno, node.value))
            elif isinstance(node, ast.JoinedStr):
                # Une f-string : on ne garde que ses morceaux littéraux, et elle sera
                # écartée plus bas si la projection en devient ambiguë.
                textes.append((node.lineno, "".join(
                    v.value for v in node.values
                    if isinstance(v, ast.Constant) and isinstance(v.value, str))))
        for lineno, texte in textes:
            m = _SELECT.search(texte)
            if not m:
                continue
            if texte.upper().count(" FROM ") != 1:
                continue                                     # jointure ou sous-requête
            cols = [c.strip().lower() for c in m.group("cols").split(",")]
            if not cols or any(not _PLAIN.match(c) for c in cols):
                continue                                     # `*`, fonction, alias…
            out.append((str(path.relative_to(_ROOT)).replace("\\", "/"),
                        lineno, m.group("table").lower(), cols))
    return out


def _schema() -> dict[str, set[str]]:
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    try:
        rows = db.fetch_query(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'")
    finally:
        db.close()
    out: dict[str, set[str]] = {}
    for table, column in rows:
        out.setdefault(table, set()).add(column)
    return out


def test_the_scan_reads_real_queries() -> None:
    """Anti-vacuité : sans projection lisible, tout ce fichier est vert sur rien."""
    found = _unambiguous_projections()
    assert len(found) >= 3, (
        f"seulement {len(found)} projection(s) SQL non ambiguë(s) lues dans `src/api/` — "
        "il y en avait 5 le 2026-09-18, dont les onze colonnes de la requête de "
        "connexion. Le lecteur est cassé, ou les requêtes ont changé de forme.")
    assert any("auth" in rel for rel, _, _, _ in found), (
        "la requête de CONNEXION n'est plus lue. C'est la seule que "
        "`test_api_db_smoke.py` ne peut pas atteindre — il forge son jeton — donc "
        "c'est la seule que ce fichier est seul à garder.")


def test_no_api_query_selects_a_column_the_schema_does_not_have() -> None:
    schema = _schema()
    fautives = []
    for rel, lineno, table, cols in _unambiguous_projections():
        if table not in schema:
            fautives.append(f"{rel}:{lineno} — table `{table}` absente de la base")
            continue
        manquantes = [c for c in cols if c not in schema[table]]
        if manquantes:
            fautives.append(f"{rel}:{lineno} — `{table}` n'a pas {manquantes}")
    assert not fautives, (
        f"{len(fautives)} requête(s) de l'API nomment une colonne que le schéma n'a "
        "pas. L'endpoint rend 500 pour TOUS les locataires, et la suite mockée ne peut "
        "pas le voir : un `MagicMock` répond à n'importe quelle colonne.\n  "
        + "\n  ".join(fautives))
