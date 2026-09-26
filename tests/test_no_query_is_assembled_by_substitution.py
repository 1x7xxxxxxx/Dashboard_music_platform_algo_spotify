"""No SQL query is built by running `.replace()` over another query.

Type: Sub
Uses: src/, tools/, airflow/ (read as AST, never imported)
Depends on: nothing — no database
Persists in: nothing

Class `a-query-assembled-by-string-substitution`. `_SQL_CUMULATIVE_ALL` was first
built by chained `.replace()` calls over `_SQL_YT_CUMULATIVE` and `_SQL_SC_CUMULATIVE`;
the CTEs of the two branches got mixed, and the SQL produced was syntactically valid
and semantically empty. The guard that caught it compares the merged query with the
single ones against a live base — it skips without Postgres, and it only watches
that one query. The gesture itself was named "nulle part balayé" in the class: this
file sweeps it across the tree.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCOPE = ("src", "tools", "airflow")


def _is_query(value: object) -> bool:
    return isinstance(value, str) and "select" in value.lower()


def substituted_queries(source: str) -> list[tuple[int, str]]:
    """(line, target) of module-level assignments that call `.replace()` on a query.

    A receiver is a query when it is a string literal holding `SELECT`, or a name the
    module binds to one (directly, or to another query-named `_SQL*` constant). Pure.
    """
    tree = ast.parse(source)
    queries = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if (isinstance(node.value, ast.Constant) and _is_query(node.value.value)) \
                    or any(n.startswith("_SQL") for n in names):
                queries.update(names)
    out = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for call in ast.walk(node.value):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "replace"):
                continue
            # A chain needs no unwinding: `ast.walk` reaches its innermost call,
            # whose receiver is the query it started from.
            recv = call.func.value
            if (isinstance(recv, ast.Name) and recv.id in queries) or \
                    (isinstance(recv, ast.Constant) and _is_query(recv.value)):
                target = next((t.id for t in node.targets if isinstance(t, ast.Name)), "?")
                out.append((node.lineno, target))
                break
    return out


def test_no_module_assembles_a_query_by_substitution() -> None:
    offenders = []
    for root in _SCOPE:
        for path in sorted((_ROOT / root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                hits = substituted_queries(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            offenders += [f"{path.relative_to(_ROOT).as_posix()}:{line} — {target}"
                          for line, target in hits]
    assert not offenders, (
        "Requête fabriquée en appliquant `.replace()` à une autre requête :\n  "
        + "\n  ".join(offenders)
        + "\n\nC'est ainsi que les CTE de `_SQL_CUMULATIVE_ALL` se sont mélangées : un "
          "SQL valide et vide. Écris la requête en entier, ou compose des morceaux "
          "NOMMÉS dont chacun est une requête lisible.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the 2026-09 shape — a merged query built by chained `.replace()`
    over two named queries — is named, so is `.replace()` on an inline SELECT; a
    `.replace()` on a non-query string, the same call inside a function body, and a
    query written in full are not."""
    merged = ('_SQL_YT = "WITH per_day AS (SELECT 1) SELECT * FROM per_day"\n'
              '_SQL_SC = "WITH per_day AS (SELECT 2) SELECT * FROM per_day"\n'
              '_SQL_ALL = (_SQL_YT.replace("per_day", "yt_day").replace("WITH", "")\n'
              '            + " UNION ALL " + _SQL_SC)\n')
    assert substituted_queries(merged) == [(3, "_SQL_ALL")]
    inline = 'Q = "SELECT a FROM t".replace("t", "u")\n'
    assert substituted_queries(inline) == [(1, "Q")]
    fine = ('LABEL = "Vues YouTube".replace("YouTube", "SoundCloud")\n'
            '_SQL_ALL = "SELECT a FROM t UNION ALL SELECT a FROM u"\n'
            'def f(q):\n    return q.replace("t", "u")\n'
            # Inside a function body it is a template filled per call — the
            # identifier class `sql-fstring-identifier` owns it, deliberately.
            'def g(table):\n    q = _SQL_ALL.replace("t", table)\n    return q\n')
    assert substituted_queries(fine) == []
