"""The stable key of a chart site — `file::function#n` — computed at RUNTIME from its caller.

Type: Utility
Uses: ast, sys (the caller's frame)
Depends on: nothing in the app — pure source reading
Persists in: a module-level cache of parsed files (once per process, never per rerun)

R314 (2026-09-28). Every chart says, under the figure, what it lets the artist decide in
managing marketing campaigns (`src/dashboard/content/chart_decisions.py`). The line is looked
up by the SAME key the review dossier uses (`tools/dev/charts_dossier/inventory.py`): the
enclosing function and the rank of the figure call among that function's figure calls, in
source order. `tests/test_every_chart_says_what_it_lets_you_decide.py` proves the runtime key
equals the static one for every site, so the two can never drift apart.

A helper drawn by several pages (`render_platform_chart`) resolves to the helper's key; a page
that needs its own line passes `decision_key=` to the door instead (code-critic, R314).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
#: The figure calls the dossier counts (gold_coverage `_FIGURE_CALLS` on `st.`/`charts.`).
_FIGURE_CALLS = frozenset({"plotly_chart", "pyplot", "bar_chart", "line_chart", "area_chart",
                           "altair_chart", "map", "graphviz_chart"})
_RECEIVERS = frozenset({"st", "charts"})
#: rel path -> {figure-call line: key}. Parsed ONCE per process: a Streamlit rerun happens
#: on every widget change, and re-parsing a view each time would be pure waste.
_KEYS: dict[str, dict[int, str]] = {}


def _enclosing(parents: dict[int, ast.AST], node: ast.AST):
    cur = parents.get(id(node))
    while cur is not None and not isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
        cur = parents.get(id(cur))
    return cur


def keys_of_source(rel: str, source: str) -> dict[int, str]:
    """{line of a figure call: its key} for one file. Pure."""
    tree = ast.parse(source)
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    per_fn: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in _FIGURE_CALLS
                and isinstance(node.func.value, ast.Name) and node.func.value.id in _RECEIVERS):
            continue
        fn = _enclosing(parents, node)
        if fn is None:
            continue
        per_fn.setdefault(fn.name, []).append(node.lineno)
    return {line: f"{rel}::{fn}#{i}"
            for fn, lines in per_fn.items() for i, line in enumerate(sorted(lines), 1)}


def key_at(rel: str, line: int) -> str | None:
    """The key of the figure call at `rel:line`, or None when there is none there."""
    if rel not in _KEYS:
        try:
            _KEYS[rel] = keys_of_source(rel, (_ROOT / rel).read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            _KEYS[rel] = {}
    return _KEYS[rel].get(line)


def caller_key(depth: int = 2) -> str | None:
    """The key of the figure call that called the door `depth` frames up."""
    frame = sys._getframe(depth)
    try:
        rel = Path(frame.f_code.co_filename).resolve().relative_to(_ROOT).as_posix()
    except ValueError:
        return None
    return key_at(rel, frame.f_lineno)
