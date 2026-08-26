"""A class whose guard has been deleted is an unguarded class that still reads guarded.

Measured 2026-08-26. The working tree carried an uncommitted change removing four
tests from `tests/test_claude_config_floor.py`. Three of them are named, by node id,
as the `guard:` or `signature:` of a catalogued error class:

    trigger-threshold-split      → test_the_build_error_threshold_agrees_across_its_three_surfaces
    rex-delimiter-unanchored     → test_the_rex_parser_survives_rst_underlines
    config-path-dangling         → test_every_claude_path_named_in_configuration_resolves

`error-classes.md` still said `status: guarded` for all three. Nothing failed: the
catalogue is prose, and prose does not notice that the file it points at has changed.
Only `audit_runner` saw it, and only because someone ran it by hand — the same shape
as `config-path-dangling` itself, one level up: a reference that misses without
complaining.

This is the cheapest possible check and it belongs in the suite, not in a nightly
report: a `pytest …::node` that does not resolve, or a guard file that is not on disk,
means the class it protects is open right now.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
CATALOGUE = REPO / ".claude" / "dev-docs" / "error-classes.md"
TEXT = CATALOGUE.read_text(encoding="utf-8")

# `tests/foo.py::test_bar`, but ONLY on the structured field lines of a class.
#
# The first version scanned the whole document and immediately failed on
# `tests/x.py::TestFoo` — an ILLUSTRATIVE example written in the prose of a class's
# own History block. Fourth time in one day that a guard matched its own
# documentation. The fields are the contract; `History:` bullets (indented, so not
# matched by `^- `) are commentary and may name anything.
_FIELD = re.compile(r"^- (?:signature|guard|long_term_fix):.*$", re.M)
_NODE_IN = re.compile(r"(tests/[A-Za-z0-9_/]+\.py)::([A-Za-z0-9_]+)")
# `guard: { type: …, ref: <path> … }` — the path half only.
_GUARD_REF = re.compile(r"^- guard:.*ref:\s*([^,}\s]+)", re.M)


def _fields() -> str:
    return "\n".join(_FIELD.findall(TEXT))


def _named_nodes() -> list[tuple[str, str]]:
    return sorted(set(_NODE_IN.findall(_fields())))


def _guard_paths() -> list[str]:
    out = set()
    for ref in _GUARD_REF.findall(TEXT):
        path = ref.split("::")[0].strip()
        if "/" in path and not path.startswith(("http", "<")):
            out.add(path)
    return sorted(out)


def test_the_catalogue_actually_names_guards():
    """Non-vacuity: both parsers below are regexes over prose and can silently
    match nothing after a formatting change."""
    assert len(_named_nodes()) >= 10, (
        f"only {len(_named_nodes())} pytest node id(s) parsed out of the catalogue — "
        "the format moved and this guard is now blind")
    assert len(_guard_paths()) >= 20, f"only {len(_guard_paths())} guard path(s) parsed"


@pytest.mark.parametrize("rel", _guard_paths())
def test_every_file_a_class_names_as_its_guard_is_on_disk(rel):
    assert (REPO / rel).exists(), (
        f"a class names {rel} as its guard and the file is not there — the class is "
        "open while the catalogue still reads `guarded`")


@pytest.mark.parametrize("rel, node", _named_nodes())
def test_every_test_a_class_names_still_exists(rel, node):
    """Resolved from the AST, not by running pytest: this must be fast and must not
    depend on the test passing today — only on it being there to fail."""
    path = REPO / rel
    assert path.exists(), f"{rel} is gone, and a class points at {node} inside it"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # `ClassDef` aussi : `tests/x.py::TestFoo` est un nœud pytest parfaitement
    # valide, et ne collecter que les fonctions faisait échouer ce garde sur une
    # référence PARFAITEMENT bonne — un faux positif dans le garde qui traque les
    # références mortes aurait été la meilleure façon de le faire désactiver.
    names = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    assert node in names, (
        f"{rel}::{node} is named by an error class and no longer exists. Deleting a "
        "guard silently re-opens the class it was closing; if the guard is genuinely "
        "obsolete, retire the class in the same change.")
