"""A WRITE is sent through `execute_query`, never through a READ method (`fetch_query`,
`fetch_df`) — unless it says `RETURNING`.

Type: Test
Uses: src/, airflow/dags/, tools/, .claude/scripts/ (parsed with ast)

Found 2026-09-28 by clicking every button (R271, note L164): `fetch_query` runs the
statement, then calls `cursor.fetchall()`, which raises `ProgrammingError: no results to
fetch` on an INSERT/UPDATE without RETURNING — AFTER the write (autocommit). The sweep
(sibling-sweeper, 618 calls → 22 candidates → 14 with RETURNING → **8 live sites**) found:
- promo_admin: « Create code » and « Disable » wrote, then the page crashed;
- register (six sites, P1): a sign-up with a promo or referral code was WRITTEN, then the
  global `except` said « L'inscription n'a pas abouti » and the verification mail was
  never sent.

Mutation record (2026-09-28) : one register.py site put back on `fetch_query` → red ;
`RETURNING` ignored by the detector → the synthetic RETURNING case went red.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ROOTS = ("src", "airflow/dags", "tools", ".claude/scripts")
_WRITE = re.compile(r"^\s*(?:--[^\n]*\n\s*)*(INSERT|UPDATE|DELETE|TRUNCATE|ALTER|CREATE|DROP)\b",
                    re.I)


def _sql_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return None


def writes_through_reads(tree: ast.AST) -> list[int]:
    """Lines of `x.fetch_query/fetch_df(<write without RETURNING>, …)`. Pure."""
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("fetch_query", "fetch_df") and n.args):
            sql = _sql_text(n.args[0])
            if sql and _WRITE.match(sql) and not re.search(r"\bRETURNING\b", sql, re.I):
                out.append(n.lineno)
    return out


def test_no_write_goes_through_a_read_method():
    live = []
    for base in _ROOTS:
        for p in sorted((ROOT / base).rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            live += [f"{p.relative_to(ROOT)}:{ln}"
                     for ln in writes_through_reads(ast.parse(p.read_text(encoding="utf-8")))]
    assert not live, (f"écriture envoyée par une méthode de LECTURE : {live} — "
                      "`execute_query`, ou ajouter `RETURNING` si le résultat est lu")


def test_the_detector_sees_the_defect_and_spares_returning_not_vacuous():
    code = (
        'db.fetch_query("INSERT INTO t (a) VALUES (%s)", (1,))\n'
        'db.fetch_query("""\n    UPDATE t SET a = 1 WHERE id = %s\n""", (1,))\n'
        'db.fetch_query("INSERT INTO t (a) VALUES (%s) RETURNING id", (1,))\n'
        'db.fetch_query("SELECT a FROM t")\n'
        'db.execute_query("INSERT INTO t (a) VALUES (%s)", (1,))\n')
    assert writes_through_reads(ast.parse(code)) == [1, 2]
