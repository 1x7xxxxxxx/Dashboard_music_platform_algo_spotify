"""A DB connection opened by a view is closed on EVERY path out of it.

Type: Test
Uses: ast
Depends on: src/dashboard/**/*.py
Persists in: nothing

Why this exists
---------------
Found 2026-09-11 while measuring how many simultaneous users the architecture
supports. Four sites opened a connection and could leave the function without
closing it:

    src/dashboard/utils/__init__.py:110   view_session()
    src/dashboard/views/alerts.py:329     show()
    src/dashboard/views/db_health.py:384  show()
    src/dashboard/views/spotify_s4a_combined.py:23  show()

Three shared one shape: `db = get_db_connection()`, then `st.stop()` — which
raises `StopException` — on a path that sat BETWEEN the open and the `try`, so
the `finally: db.close()` never ran. The fourth closed at plain function-body
indentation, ~290 lines after the open, guarded by nothing.

None of this costs anything with one user: the process is short-lived and the
socket dies with it. It costs at the next tier. `max_connections` is the stock
100, shared with Airflow and an API that can hold 40 at once, so roughly 27 are
left for the dashboard — and a leak there does not show up as slowness, it shows
up as a refused connection.

Why AST and not a grep
----------------------
The question is "can this function be left while holding an open connection?",
which is a statement-order property. No string search expresses it. And the
first version of this predicate, written the same hour, flagged `project_db()`
— whose only early exit is `if db is None: st.stop()`, where by construction
nothing is open. A predicate that matches the symptom ("there is a stop") rather
than the question ("can we leave holding a connection") reports a site that is
correct. `_tests_absent` is that correction.

Mutation record — 2026-09-11: run against the tree before the fix, this guard
reported 4 sites and exited non-zero; after the fix, 0. It has been seen red on
the defect it exists to catch.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_DASHBOARD = _ROOT / "src" / "dashboard"

# Functions that hand back a live connection the caller must close itself.
# `project_db()` / `view_session()` are context managers and are not openers:
# a `with` block closes on every path, which is the whole point of using them.
_OPENERS = {"get_db_connection"}


def _closes(node: ast.AST, name: str) -> bool:
    """Does this subtree call `name.close()`?"""
    return any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "close"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == name
        for n in ast.walk(node)
    )


def _tests_absent(test: ast.expr, name: str) -> bool:
    """Is this `if` test asserting `name` holds no connection?

    `if db is None:` and `if not db:` both mean the open failed, so an exit
    underneath them leaks nothing.
    """
    if (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == name
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Is)
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    ):
        return True
    return (
        isinstance(test, ast.UnaryOp)
        and isinstance(test.op, ast.Not)
        and isinstance(test.operand, ast.Name)
        and test.operand.id == name
    )


def _exits_holding(stmt: ast.stmt, name: str) -> bool:
    """Can this statement leave the function WHILE `name` is open?"""
    if isinstance(stmt, ast.If) and _tests_absent(stmt.test, name):
        return False
    if isinstance(stmt, (ast.Return, ast.Raise)):
        return True
    for n in ast.walk(stmt):
        if isinstance(n, (ast.Return, ast.Raise)):
            return True
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "stop"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "st"
        ):
            return True
    return False


def _scan(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rel = path.relative_to(_ROOT)
    found: list[str] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for i, stmt in enumerate(fn.body):
            if not (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call)):
                continue
            func = stmt.value.func
            called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if called not in _OPENERS:
                continue
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                continue
            var = stmt.targets[0].id
            rest = fn.body[i + 1:]
            guard = next(
                (s for s in rest
                 if isinstance(s, ast.Try) and any(_closes(x, var) for x in s.finalbody)),
                None,
            )
            if guard is None:
                found.append(
                    f"{rel}:{stmt.lineno} {fn.name}() — `{var}` is opened and no "
                    f"try/finally closes it. Use `with project_db() as {var}:`."
                )
                continue
            leaking = [s for s in rest[:rest.index(guard)] if _exits_holding(s, var)]
            if leaking:
                found.append(
                    f"{rel}:{stmt.lineno} {fn.name}() — `{var}` is open at line "
                    f"{leaking[0].lineno}, which can leave the function before the "
                    f"try at line {guard.lineno}, so its finally never runs. "
                    f"Resolve the tenant BEFORE opening the connection."
                )
    return found


def test_no_dashboard_connection_can_escape_unclosed() -> None:
    offenders = [
        msg
        for path in sorted(_DASHBOARD.rglob("*.py"))
        for msg in _scan(path)
    ]
    assert not offenders, (
        "A connection can be left open on some path out of these functions.\n"
        "Harmless with one user; at the next tier they accumulate against the\n"
        "stock max_connections=100 shared with Airflow and the API.\n\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize(
    "source, expect_hit",
    [
        # The shape that leaked: open, then a stop that precedes the try.
        ("""
def show():
    db = get_db_connection()
    if artist_id is None:
        st.stop()
    try:
        use(db)
    finally:
        db.close()
""", True),
        # The fix: resolve first, so the stop happens with nothing open.
        ("""
def show():
    if artist_id is None:
        st.stop()
    db = get_db_connection()
    try:
        use(db)
    finally:
        db.close()
""", False),
        # No try/finally at all.
        ("""
def show():
    db = get_db_connection()
    use(db)
    db.close()
""", True),
        # `if db is None: st.stop()` leaks nothing — the predicate must not
        # report it. This case is why the guard reads the test, not the stop.
        ("""
def project_db():
    db = get_db_connection()
    if db is None:
        st.stop()
    try:
        yield db
    finally:
        db.close()
""", False),
    ],
)
def test_the_predicate_separates_the_defect_from_its_look_alike(
    source: str, expect_hit: bool, tmp_path: pathlib.Path
) -> None:
    """The guard must fire on the defect and stay quiet on the correct form.

    Without this, a predicate that simply looked for `st.stop()` would pass the
    suite while reporting `project_db()`, which is right as written.
    """
    target = tmp_path / "sample.py"
    target.write_text(source, encoding="utf-8")

    tree = ast.parse(source)
    rel_scan: list[str] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for i, stmt in enumerate(fn.body):
            if not (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call)):
                continue
            func = stmt.value.func
            if getattr(func, "id", None) not in _OPENERS:
                continue
            var = stmt.targets[0].id
            rest = fn.body[i + 1:]
            guard = next(
                (s for s in rest
                 if isinstance(s, ast.Try) and any(_closes(x, var) for x in s.finalbody)),
                None,
            )
            if guard is None or any(_exits_holding(s, var) for s in rest[:rest.index(guard)]):
                rel_scan.append(fn.name)

    assert bool(rel_scan) is expect_hit, (
        f"predicate returned {rel_scan!r}, expected hit={expect_hit} for:\n{source}"
    )
