"""Quelles tables portent un locataire — déduit du SCHÉMA, jamais énuméré.

Type: Utility
Uses: re, pathlib
Triggers: .claude/scripts/audit_tenant_writes.py, tools/create_sandbox.py
Depends on: init_db.sql, migrations/*.sql
Persists in: nothing

Pourquoi ce module existe ici et pas ailleurs — mesuré le 2026-09-18
--------------------------------------------------------------------
`tenant_scoped_tables()` vivait dans `.claude/scripts/audit_tenant_writes.py`, et
`tools/create_sandbox.py` allait l'importer de là. **Ça aurait cassé en conteneur :**
`.dockerignore:50` exclut `.claude/` de tout contexte Docker, et les trois services
Airflow bind-montent `./tools` (`:ro`) et `./src` — jamais `.claude/`. Un outil de
production qui importe de l'outillage Claude Code lève `ModuleNotFoundError` dès qu'il
tourne là où il doit tourner.

La règle qui en sort : `src/` et `tools/` sont embarqués, `.claude/` ne l'est pas. La
dépendance va donc toujours de `.claude/` vers `src/`, jamais l'inverse.

Ce que la fonction distingue, et pourquoi c'est le TYPE
-------------------------------------------------------
`artist_id` ne désigne pas toujours le locataire. Sur `artists`, `artist_history` et
`tracks` c'est l'identifiant Spotify (VARCHAR), et le locataire y est `saas_artist_id`
(INTEGER). On raisonne donc sur le type déclaré, jamais sur le nom — c'est la règle de
`.claude/rules/python.md`, section « Le locataire ».
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_VARCHAR = re.compile(r"(?:VARCHAR|TEXT|CHAR)", re.I)

_CREATE = re.compile(
    r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)\s*\((.*?)\n\s*\);", re.S | re.I)
_ALTER = re.compile(
    r"ALTER TABLE\s+(\w+)\s+ADD COLUMN(?:\s+IF NOT EXISTS)?\s+"
    r"(artist_id|saas_artist_id)([^,;\n]*)", re.I)


def tenant_scoped_tables() -> dict[str, str]:
    """{table: colonne QUI PORTE LE LOCATAIRE}, déduite du TYPE déclaré.

    Une table dont le seul `artist_id` est un VARCHAR (identifiant de plateforme) et
    qui n'a pas de `saas_artist_id` n'est PAS scopée-locataire : c'est une table de
    référence globale, et l'exiger d'elle serait un faux positif.
    """
    tables: dict[str, str] = {}
    sources = [_ROOT / "init_db.sql"] + sorted((_ROOT / "migrations").glob("*.sql"))
    for path in sources:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, body in _CREATE.findall(text):
            table = name.lower()
            for col in ("saas_artist_id", "artist_id"):
                m = re.search(rf"^\s*{col}\s+([^,\n]*)", body, re.M | re.I)
                if not m:
                    continue
                # `saas_artist_id` est le locataire par construction ; `artist_id` ne
                # l'est que s'il est ENTIER.
                if col == "saas_artist_id" or not _VARCHAR.search(m.group(1)):
                    tables[table] = col
                    break
        for name, col, decl in _ALTER.findall(text):
            table, col = name.lower(), col.lower()
            if col == "saas_artist_id" or not _VARCHAR.search(decl):
                # Une colonne ajoutée après coup NE DÉCLASSE PAS un locataire déjà
                # trouvé : `saas_artist_id` l'emporte sur `artist_id`.
                if tables.get(table) != "saas_artist_id":
                    tables[table] = col
    return tables
