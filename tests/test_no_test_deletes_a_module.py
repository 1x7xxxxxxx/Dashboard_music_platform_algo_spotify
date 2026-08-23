"""
Guard — a test may borrow global state, never leave a hole where it found something.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: tests/**
Persists in: nothing

Error class: test-leaves-a-hole-in-sys-modules.

Measured 2026-08-23. `tests/test_readiness_carries_the_live_diagnosis.py` stubbed
`sys.modules["src.dashboard.views.credentials._registry"]` and, in its `finally`, called
`del` instead of restoring the previous value. Deleting the key evicts the real module
for the REST OF THE SESSION: the next import re-executes it from disk and hands out a
second module object, while everything that already did `from … import NAME` keeps the
first. A later `monkeypatch.setattr("pkg.mod.NAME", …)` then patches one object while the
code under test reads the other.

The symptom in CI was `test_a_raising_probe_becomes_a_red_not_a_traceback` failing with
the five REAL probes in its output, despite a monkeypatch to a single fake one — a test
that had nothing to do with the offender, in a different file.

This trap is invisible to any single-file run, because the test that causes it always
passes. That is why it needs a structural guard rather than a test.
"""

import ast
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent


def _test_files() -> list[str]:
    return sorted(p.name for p in TESTS.glob("test_*.py"))


def _evictions(path: Path) -> list[int]:
    """`del sys.modules[…]`, and `sys.modules.pop` with no saved previous value."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad: list[int] = []

    # A function that saves the previous value is doing the right thing; the `pop` in
    # its restore branch is the correct ending, not the defect.
    saves_previous = any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get"
        and isinstance(n.func.value, ast.Attribute)
        and n.func.value.attr == "modules"
        for n in ast.walk(tree)
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Delete):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Subscript)
                        and isinstance(tgt.value, ast.Attribute)
                        and tgt.value.attr == "modules"):
                    bad.append(node.lineno)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "pop"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "modules"
                and not saves_previous):
            bad.append(node.lineno)
    return sorted(set(bad))


def test_the_scope_is_not_empty() -> None:
    assert len(_test_files()) > 50, "the test walk found almost nothing"


@pytest.mark.parametrize("name", _test_files())
def test_a_test_restores_what_it_borrows_from_sys_modules(name: str) -> None:
    bad = _evictions(TESTS / name)
    assert not bad, (
        f"{name} removes an entry from sys.modules at line(s) {bad} instead of restoring "
        f"the previous value. That evicts the real module for the rest of the session, "
        f"and the next import hands out a SECOND object — so a later monkeypatch patches "
        f"one while the code reads the other. Save it first:\n"
        f"    previous = sys.modules.get(key)\n"
        f"    ...\n"
        f"    if previous is not None: sys.modules[key] = previous\n"
        f"    else: sys.modules.pop(key, None)"
    )
