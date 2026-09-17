#!/usr/bin/env python3
"""Every write to a tenant-scoped table must name its tenant. AST + SQL scan.

Type: Utility (error-class guard)
Uses: ast, re, init_db.sql + migrations/*.sql (to learn which tables are tenant-scoped)
Triggers: `python3 .claude/scripts/audit_tenant_writes.py`, and audit_runner via the
    `write-without-explicit-artist-id` signature
Persists in: nothing

`track_popularity_history` stored EVERY tenant's Spotify popularity history under
the admin for months: the payload had no `artist_id` key, `upsert_many` derives the
INSERT column list from the payload keys, and the column carries `DEFAULT 1`. No
error, no alert — Postgres filled it in.

This finds the whole class rather than that one instance:

  * `INSERT INTO <tenant table> (cols…)` whose column list omits artist_id
  * `upsert_many(table='<tenant table>', data=<list built from dict literals>)`
    where none of those literals carries an artist_id key

Only literal, locally-resolvable payloads are judged — an unresolvable one is
reported as UNKNOWN (visible, not silently passed). Exit 1 on any MISSING.

---
rex:
  - date: 2026-08-20
    issue: "A tenant-scoped write with no artist_id key does not fail. upsert_many derives the INSERT column list from the payload keys, and the column carried DEFAULT 1, so Postgres filled in the admin. track_popularity_history stored every tenant's Spotify history under artist_id=1 for months with no error and no alert."
    fix: "Scan is AST-based on the payload, not textual: a dict literal missing the key is MISSING, an unresolvable payload is UNKNOWN and stays visible rather than passing. Wired into audit_runner via the write-without-explicit-artist-id signature, so it runs in CI instead of on request."
    ref: "DEVLOG#2026-08-20"
    severity: crit
  - date: 2026-08-21
    issue: "Written 2026-08-20 but never committed — it lived in the working tree alone, alongside five migrations and fourteen test files. A `git checkout .` would have deleted the whole P1 fix, guard included."
    fix: "Committed (83d3c63). The durable lesson is not about this file: check `git status` before believing a piece of work exists. Three sessions of P1 work were never on any branch."
    ref: "R26"
    severity: warn
---
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCAN_DIRS = ("src", "airflow/dags")
_TENANT_KEYS = {"artist_id", "saas_artist_id"}


# ── Le TYPE, jamais le nom ───────────────────────────────────────────────────
#
# ⚠️ Corrigé le 2026-09-17, et c'est cet outil-ci que `.claude/rules/python.md`
# NOMME comme garde de la règle qu'il enfreignait :
#
#   « `artist_id` n'est pas toujours le locataire : sur `artists`,
#     `artist_history` et `tracks`, c'est l'identifiant Spotify (VARCHAR) — le
#     locataire y est `saas_artist_id` (INTEGER). On raisonne sur le TYPE,
#     jamais sur le nom. Garde : audit_tenant_writes.py »
#
# Il faisait exactement l'inverse : `if keys & {"artist_id", "saas_artist_id"}`,
# donc N'IMPORTE LAQUELLE des deux suffisait. Mesuré ce jour-là : `artists`,
# `tracks` et `artist_history` étaient comptées parmi ses **83 tables
# scopées-locataire** à cause du NOM de leur colonne, alors que deux d'entre
# elles n'ont aucun locataire, et que sur `tracks` une écriture portant le seul
# `artist_id` Spotify serait passée au vert **sans propriétaire**.
#
# Aucune écriture réelle n'en profitait — `spotify_api_daily.py:363` pose bien
# `saas_artist_id` — donc c'était un trou de GARDE, pas un défaut de données.
# C'est précisément la forme qui survit : rien ne rougit.
_VARCHAR = re.compile(r"(?:VARCHAR|TEXT|CHAR)", re.I)


def tenant_scoped_tables() -> dict[str, str]:
    """{table: colonne QUI PORTE LE LOCATAIRE}, déduite du TYPE déclaré.

    Une table dont le seul `artist_id` est un VARCHAR (identifiant de plateforme)
    et qui n'a pas de `saas_artist_id` n'est PAS scopée-locataire : elle est une
    table de référence globale, et l'exiger d'elle serait un faux positif.
    """
    tables: dict[str, str] = {}
    sources = [_ROOT / "init_db.sql"] + sorted((_ROOT / "migrations").glob("*.sql"))
    create_re = re.compile(
        r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)\s*\((.*?)\n\s*\);",
        re.S | re.I)
    alter_re = re.compile(
        r"ALTER TABLE\s+(\w+)\s+ADD COLUMN(?:\s+IF NOT EXISTS)?\s+(artist_id|saas_artist_id)"
        r"([^,;\n]*)",
        re.I)
    for path in sources:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, body in create_re.findall(text):
            table = name.lower()
            for col in ("saas_artist_id", "artist_id"):
                m = re.search(rf"^\s*{col}\s+([^,\n]*)", body, re.M | re.I)
                if not m:
                    continue
                # `saas_artist_id` est le locataire par construction ; `artist_id`
                # ne l'est que s'il est ENTIER.
                if col == "saas_artist_id" or not _VARCHAR.search(m.group(1)):
                    tables[table] = col
                    break
        for name, col, decl in alter_re.findall(text):
            table, col = name.lower(), col.lower()
            if col == "saas_artist_id" or not _VARCHAR.search(decl):
                # Une colonne ajoutée après coup NE DÉCLASSE PAS un locataire déjà
                # trouvé : `saas_artist_id` l'emporte sur `artist_id`.
                if tables.get(table) != "saas_artist_id":
                    tables[table] = col
    return tables


def _dict_keys(node: ast.AST) -> tuple[set[str], bool] | None:
    """(explicit keys, complete?) of a dict literal. None if it is not a dict.

    `complete=False` means part of the dict came from an opaque `**spread`, so the
    key set is a LOWER BOUND. That distinction is what keeps the guard usable:
    seeing `artist_id` among the explicit keys is proof enough, whatever the
    spread contains — only its ABSENCE is then inconclusive.
    """
    if not isinstance(node, ast.Dict):
        return None
    keys: set[str] = set()
    complete = True
    for key, value in zip(node.keys, node.values):
        if key is None:  # {**something}
            inner = _dict_keys(value)
            if inner is None:
                complete = False
            else:
                keys |= inner[0]
                complete = complete and inner[1]
        elif isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
        else:
            complete = False
    return keys, complete


def _payload_keys(node: ast.AST, scope: dict[str, ast.AST],
                  depth: int = 0) -> tuple[set[str], bool] | None:
    """(keys, complete?) carried by the value passed as `data=`, if resolvable."""
    if depth > 4 or node is None:
        return None
    if isinstance(node, ast.Name):
        target = scope.get(node.id)
        return _payload_keys(target, scope, depth + 1) if target is not None else None
    if isinstance(node, ast.List):
        merged: set[str] = set()
        complete = True
        for element in node.elts:
            inner = _payload_keys(element, scope, depth + 1)
            if inner is None:
                complete = False
                continue
            merged |= inner[0]
            complete = complete and inner[1]
        return merged, complete if node.elts else True
    if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
        return _payload_keys(node.elt, scope, depth + 1)
    if isinstance(node, ast.Dict):
        return _dict_keys(node)
    if isinstance(node, ast.Call):
        # e.g. list(...) / [*rows] wrappers — unresolvable, but not a dict literal
        return None
    return None


def _scope_assignments(tree: ast.AST) -> dict[str, ast.AST]:
    """name -> last assigned value, plus names extended via `.append(<dict>)`."""
    scope: dict[str, ast.AST] = {}
    appended: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    scope[target.id] = node.value
        elif (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "append"
                and isinstance(node.func.value, ast.Name)
                and node.args):
            appended.setdefault(node.func.value.id, []).append(node.args[0])
    for name, values in appended.items():
        # A list built by .append(dict literal) — model it as a list of those dicts.
        scope[name] = ast.List(elts=values, ctx=ast.Load())
    return scope


_INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+(\w+)\s*\(([^)]*)\)", re.I | re.S)


def scan_file(path: Path, tenant_tables: dict[str, str]) -> list[tuple[str, int, str]]:
    # utf-8-sig: a UTF-8 BOM made ast.parse fail on three DAGs, and every
    # AST guard that read them silently scanned nothing.
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    findings: list[tuple[str, int, str]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [("UNPARSABLE", exc.lineno or 0, f"{path}: {exc.msg}")]

    scope = _scope_assignments(tree)

    # ── upsert_many(table=…, data=…) ────────────────────────────────────────
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "attr", None) == "upsert_many"):
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords}
        table_node = kwargs.get("table") or (node.args[0] if node.args else None)
        data_node = kwargs.get("data") or (node.args[1] if len(node.args) > 1 else None)
        if not (isinstance(table_node, ast.Constant) and isinstance(table_node.value, str)):
            continue
        table = table_node.value.lower()
        if table not in tenant_tables:
            continue
        resolved = _payload_keys(data_node, scope) if data_node is not None else None
        if resolved is None:
            findings.append(("UNKNOWN", node.lineno,
                             f"{path}: upsert_many('{table}') — payload not statically "
                             f"resolvable; confirm it carries "
                             f"`{tenant_tables[table]}`"))
            continue
        keys, complete = resolved
        # ⚠️ LA colonne de CETTE table, pas « l'une des deux ». Sur `tracks`,
        # `artist_id` est l'identifiant Spotify : l'accepter laissait passer une
        # écriture SANS propriétaire.
        tenant_col = tenant_tables[table]
        if tenant_col in keys:
            continue  # proven: the tenant is named explicitly
        if complete:
            findings.append(("MISSING", node.lineno,
                             f"{path}: upsert_many('{table}') — payload keys "
                             f"{sorted(keys)} carry no `{tenant_col}` → the column "
                             "DEFAULT decides the owner"))
        else:
            findings.append(("UNKNOWN", node.lineno,
                             f"{path}: upsert_many('{table}') — `{tenant_col}` would "
                             f"have to come from a spread; explicit keys are "
                             f"{sorted(keys)}"))

    # ── raw INSERT INTO <table> (columns…) ──────────────────────────────────
    for match in _INSERT_RE.finditer(text):
        table = match.group(1).lower()
        if table not in tenant_tables:
            continue
        columns = {c.strip().strip('"').lower() for c in match.group(2).split(",")}
        tenant_col = tenant_tables[table]
        if tenant_col not in columns:
            line = text[:match.start()].count("\n") + 1
            findings.append(("MISSING", line,
                             f"{path}: INSERT INTO {table} ({', '.join(sorted(columns))}) "
                             f"— no `{tenant_col}`"))
    return findings


def main() -> int:
    tenant_tables = tenant_scoped_tables()
    if not tenant_tables:
        print("❌ could not determine tenant-scoped tables from the SQL sources")
        return 2

    findings: list[tuple[str, int, str]] = []
    for directory in _SCAN_DIRS:
        for path in sorted((_ROOT / directory).rglob("*.py")):
            findings += scan_file(path, tenant_tables)

    missing = [f for f in findings if f[0] == "MISSING"]
    unknown = [f for f in findings if f[0] == "UNKNOWN"]
    unparsable = [f for f in findings if f[0] == "UNPARSABLE"]

    # A file the scanner cannot read is NOT a file that passed. Silently dropping
    # it is the very class this script exists to catch, one level up.
    for _kind, line, message in unparsable:
        print(f"❌ UNPARSABLE: {message} (l.{line}) — scanned nothing")

    for kind, line, message in missing + unknown:
        rel = message.replace(str(_ROOT) + "/", "")
        print(f"{'❌' if kind == 'MISSING' else '⚠️ '} {kind}: {rel} (l.{line})")

    print(f"\n{len(tenant_scoped_tables())} tenant-scoped tables scanned · "
          f"{len(missing)} missing · {len(unknown)} unresolvable · "
          f"{len(unparsable)} unreadable")
    return 1 if (missing or unparsable) else 0


if __name__ == "__main__":
    sys.exit(main())
