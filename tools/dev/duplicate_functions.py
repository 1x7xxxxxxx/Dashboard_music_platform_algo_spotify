#!/usr/bin/env python3
"""List the functions written twice — same body, in one script or across scripts.

Type: Utility
Uses: src/, airflow/dags/, tools/ (parsed with ast)
Triggers: `make duplicates`, tests/test_a_function_is_written_once.py (ratchet)
Persists in: nothing (prints)

R269 (owner notes L166 : « les doublons intra et inter-scripts »). A body is compared on
its SYNTAX TREE with the docstring dropped and every literal blanked, so a comment, a
reformatting or a changed string (a table name, a log label) does not hide a copy.
Only bodies of at least `MIN_LINES` source lines and `MIN_STMTS` statements count: a
single `return db.fetch_df(<sql>, …)` differs by its SQL only, and blanking it would call two
different queries a copy (measured on the first run, 2026-09-27).
"""
from __future__ import annotations

import ast
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROOTS = ("src", "airflow/dags", "tools")
MIN_LINES = 6
MIN_STMTS = 3


class _Blank(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        return ast.Constant(value="K")


def _body_key(fn: ast.AST) -> str | None:
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    if not body or (fn.end_lineno - body[0].lineno + 1) < MIN_LINES:
        return None
    if sum(isinstance(n, ast.stmt) for b in body for n in ast.walk(b)) < MIN_STMTS:
        return None
    blank = _Blank().visit(ast.parse(ast.unparse(ast.Module(body=body, type_ignores=[]))))
    dump = ast.dump(blank, include_attributes=False)
    return hashlib.sha1((ast.dump(fn.args) + dump).encode()).hexdigest()


def groups(files: list[tuple[str, str]]) -> list[list[str]]:
    """Groups of `path:line name` sharing one body, largest first. Pure."""
    seen: dict[str, list[str]] = defaultdict(list)
    for rel, text in files:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                key = _body_key(node)
                if key:
                    seen[key].append(f"{rel}:{node.lineno} {node.name}")
    return sorted((sorted(v) for v in seen.values() if len(v) > 1), key=lambda g: (-len(g), g))


def repo_files() -> list[tuple[str, str]]:
    out = []
    for base in ROOTS:
        for p in sorted((ROOT / base).rglob("*.py")):
            if "__pycache__" not in p.parts:
                out.append((str(p.relative_to(ROOT)), p.read_text(encoding="utf-8")))
    return out


def main() -> int:
    found = groups(repo_files())
    for g in found:
        print(f"— {len(g)} copies")
        for site in g:
            print(f"    {site}")
    print(f"{len(found)} groupe(s) de fonctions dupliquées, {sum(len(g) for g in found)} sites")
    return 0


if __name__ == "__main__":
    sys.exit(main())
