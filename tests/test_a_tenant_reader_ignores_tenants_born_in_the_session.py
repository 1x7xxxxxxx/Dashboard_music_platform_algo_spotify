"""R229 — a test that lists active tenants ignores those born during the session.

The canary and the two-tenant e2e tests create ACTIVE tenants from other xdist
groups and delete them in their teardown. A reader that takes « the first active
tenant that has X », or counts active tenants, can land on one mid-life: nine
readers did, found by the sweep of 2026-09-27 (class
`a-shared-database-read-while-another-test-writes-it`). The remedy is one helper in
tests/conftest.py — `pre_session_active_tenants()` or `born_before_session()`.

Structural: a function whose SQL lists `saas_artists … WHERE … active` must either
filter on `created_at` in that SQL or call one of the two helpers.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_LISTS_ACTIVE = re.compile(r"FROM\s+saas_artists\s+(\w+\s+)?WHERE\s+(\w+\.)?active\b", re.I)
_HELPERS = {"pre_session_active_tenants", "born_before_session"}


def unfiltered_readers(tree: ast.AST) -> list[int]:
    """Lines of active-tenant SQL in a function that never filters by session birth."""
    bad = []
    # A string handed to `ast.parse` is code under test, not a query this file runs.
    parsed = {id(c) for n in ast.walk(tree) if isinstance(n, ast.Call)
              and getattr(n.func, "attr", "") == "parse" for c in ast.walk(n)}
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = {getattr(n.func, "id", getattr(n.func, "attr", ""))
                 for n in ast.walk(fn) if isinstance(n, ast.Call)}
        if calls & _HELPERS:
            continue
        for n in ast.walk(fn):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in parsed \
                    and _LISTS_ACTIVE.search(n.value) and "created_at" not in n.value:
                bad.append(n.lineno)
    return sorted(set(bad))


def test_no_test_lists_active_tenants_without_the_session_filter():
    offenders = []
    for f in sorted((ROOT / "tests").glob("*.py")):
        for line in unfiltered_readers(ast.parse(f.read_text())):
            offenders.append(f"{f.name}:{line}")
    assert not offenders, (
        "these readers can pick or count a tenant a neighbouring test is creating and "
        f"deleting: {offenders}. Use tests.conftest.pre_session_active_tenants(db) or "
        "born_before_session()."
    )


def test_the_detector_sees_the_defect_it_is_written_for():
    defect = ast.parse(
        "def f(db):\n"
        "    return db.fetch_query('SELECT id FROM saas_artists WHERE active ORDER BY id')\n")
    assert unfiltered_readers(defect), "the defect is not seen"
    fixed = ast.parse(
        "def f(db):\n"
        "    born, p = born_before_session()\n"
        "    return db.fetch_query('SELECT id FROM saas_artists WHERE active' + born, p)\n")
    assert not unfiltered_readers(fixed), "a fix would turn the guard red"
    aliased = ast.parse(
        "def f(db):\n"
        "    return db.fetch_query('SELECT a.id FROM saas_artists a WHERE a.active')\n")
    assert unfiltered_readers(aliased), "the aliased form is the same defect"
