"""Airflow state is fleet-wide. A tenant page may not show it ungated.

Type: Test
Uses: ast
Depends on: src/dashboard/views/**.py, src/dashboard/app.py (_ADMIN_ONLY)
Persists in: nothing

The class
---------
Airflow knows nothing about tenants. `get_all_dags_last_state()` answers "when did
`spotify_api_daily` last run, for anybody" — in practice, the admin's run. Shown on a
page an artist reads, it becomes a claim about THEIR data.

Three occurrences, and the third is why this file exists:

  2026-08-22  `_render_global_kpi` — a green readiness KPI whose second axis was the
              fleet's Airflow state. It read 🟢 for tenants holding zero rows. Removed.
  2026-08-30  `views/home.py::_section_dag_status` — gated on `is_admin()`.
  2026-08-30  `views/credentials/_render.py::_render_dag_status_badge` — a brand-new
              artist read "DAG spotify_api_daily — 🟢 success — dernier run : …" and
              asked whether they were seeing another artist's data. They were.

The comment above the third one asserted, in writing, that it was SAFE, for eight
days, while it was the live instance. A written claim is not a guard.

What this asserts
-----------------
Every function that calls a fleet-state reader is either (a) inside a module the app
routes as admin-only, or (b) guarded by `is_admin()` in the same function.

This is deliberately structural — a call graph question answered on the AST. Grepping
for `dag_states` would have passed all along: the string was there in both the safe
and the unsafe version.

Scope, chosen on purpose
------------------------
The readers themselves (`_fetch_dag_last_states`, `_render_dag_status_badge`) are
exempt as DEFINITIONS: a function cannot know its caller's audience, and the question
here is who RENDERS the state, not who fetches it. The first version of this file
asked "who reads it" and immediately flagged `_fetch_dag_last_states` — whose single
caller is gated. Flagging the plumbing while the leak is at the tap is how a guard
ends up disabled instead of fixed.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src/dashboard/views"
_APP = _ROOT / "src/dashboard/app.py"

# The functions that answer with FLEET state, whatever the caller's tenant.
_FLEET_READERS = {
    "get_all_dags_last_state",
    "cached_last_run_per_dag",
    "_fetch_dag_last_states",
    "_render_dag_status_badge",
}


def _admin_only_pages() -> set[str]:
    """The page keys app.py refuses to route to a non-admin."""
    body = _APP.read_text(encoding="utf-8")
    m = re.search(r"_ADMIN_ONLY\s*=\s*\{(.*?)\}", body, re.S)
    assert m, "app.py no longer defines _ADMIN_ONLY — this guard cannot tell which pages are gated"
    return set(re.findall(r"'([^']+)'", m.group(1)))


def _mentions_is_admin(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Call)
               and ((isinstance(n.func, ast.Name) and n.func.id == "is_admin")
                    or (isinstance(n.func, ast.Attribute) and n.func.attr == "is_admin"))
               for n in ast.walk(node))


def _fleet_calls(fn: ast.AST):
    """Yield every Call node inside `fn` that asks for fleet state."""
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
        if name in _FLEET_READERS:
            yield n


def _guarded_by_an_enclosing_if(fn: ast.AST, target: ast.Call) -> bool:
    """True when `target` sits inside an `if` whose TEST asks is_admin()."""
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(fn):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    cur: ast.AST | None = target
    while cur is not None and cur is not fn:
        parent = parents.get(id(cur))
        if isinstance(parent, ast.If) and _mentions_is_admin(parent.test):
            # `cur` must be in the body (or orelse of a `not is_admin()` test) —
            # being the test itself does not gate anything.
            if cur is not parent.test:
                return True
        cur = parent
    return False


def _has_early_admin_return(fn: ast.AST, target: ast.Call) -> bool:
    """True for the `if not is_admin(): return` guard clause form, before `target`."""
    for stmt in ast.walk(fn):
        if not (isinstance(stmt, ast.If) and _mentions_is_admin(stmt.test)):
            continue
        exits = any(isinstance(n, (ast.Return, ast.Raise)) for n in ast.walk(stmt))
        if exits and stmt.lineno < getattr(target, "lineno", 0):
            return True
    return False


def test_no_artist_facing_function_renders_fleet_airflow_state():
    admin_pages = _admin_only_pages()
    offenders: list[str] = []

    for path in sorted(_VIEWS.rglob("*.py")):
        # A view module is admin-only when its page key is in _ADMIN_ONLY. For a
        # package (views/credentials/router.py) the key is the directory name.
        page_key = path.parent.name if path.name == "router.py" else path.stem
        if page_key in admin_pages:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in [n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            # A reader's own definition is plumbing: it has no audience of its own.
            if fn.name in _FLEET_READERS:
                continue
            for call in _fleet_calls(fn):
                if _guarded_by_an_enclosing_if(fn, call) or _has_early_admin_return(fn, call):
                    continue
                name = getattr(call.func, "id", getattr(call.func, "attr", "?"))
                offenders.append(
                    f"{path.relative_to(_ROOT)}::{fn.name} line {call.lineno} — "
                    f"{name}() is rendered with no is_admin() gate around THIS call"
                )

    assert not offenders, (
        "fleet-wide Airflow state is rendered on a tenant surface:\n  "
        + "\n  ".join(offenders)
        + "\n\nAirflow has no notion of tenant: what these read is the last run of that "
          "DAG for ANYBODY, in practice the admin's. An artist reads it as their own "
          "collection. Either gate THIS call on is_admin(), or ask the per-tenant "
          "source instead (etl_run_log / the status matrix).\n"
          "Note: `is_admin()` appearing somewhere else in the same function does not "
          "count — that was the first version of this guard, and it stayed green on "
          "the very defect it was written for."
    )
