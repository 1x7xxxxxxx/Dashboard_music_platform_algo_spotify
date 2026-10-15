"""Dead code only shrinks: the functions nothing names are exactly the baseline (R609).

Type: Hook
Uses: tools/dev/dead_code.py (vulture, pinned in the dev extra)
Persists in: tests/dead_code_baseline.json — sorted `file::name` keys

Strict BOTH ways: a new dead function is red (delete it, or name its caller), and a
baseline entry that is no longer dead is red too (remove it from the baseline — a ratchet
that keeps stale keys lets a new defect hide behind a deleted one).

guard_scope: functions, methods, properties and classes no tracked code file names.
NOT covered: a function only tests call (`dead_code.py --without-tests` measures it),
a call by a computed name, unused variables and imports.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))
import dead_code  # noqa: E402


def test_vulture_is_installed_never_skipped() -> None:
    assert importlib.util.find_spec("vulture"), \
        "vulture is missing: `uv sync --frozen --extra dev` (a skipped ratchet guards nothing)"


def test_the_dead_functions_are_exactly_the_baseline() -> None:
    _, live = dead_code.dead_keys()
    now = {c.key for c in live}
    known = dead_code.load_baseline()
    new, gone = sorted(now - known), sorted(known - now)
    assert not new, ("functions nothing names — delete them, or name their caller:\n  "
                     + "\n  ".join(new))
    assert not gone, ("no longer dead — remove from tests/dead_code_baseline.json:\n  "
                      + "\n  ".join(gone))


_SRC = '''\
from fastapi import APIRouter
router = APIRouter()

def orphan():
    return 1

def routed_by_string():
    return 2

@router.get("/x")
def endpoint():
    return 3

@lru_cache
def cached_orphan():
    return 4
'''
_OUT = "\n".join(f"src/m.py:{n}: unused function '{name}' (60% confidence)" for n, name in
                 [(4, "orphan"), (7, "routed_by_string"), (11, "endpoint"),
                  (15, "cached_orphan")]) + "\nsrc/m.py:1: unused variable 'x' (100% confidence)"


def test_the_funnel_drops_a_named_caller_and_keeps_an_orphan() -> None:
    """Both mutation directions, on a fixture: a name cited only as a string in ANOTHER
    file is alive (false positive dropped); an undecorated, unnamed function is dead, and
    so is a cached one (false negative kept)."""
    corpus = {"src/m.py": _SRC, "src/routes.py": 'ROUTES = {"x": "routed_by_string"}'}
    funnel, live = dead_code.classify(dead_code.parse(_OUT), corpus)
    assert sorted(c.name for c in live) == ["cached_orphan", "orphan"]
    assert funnel["nommée ailleurs"] == 1 and funnel["décorateur framework"] == 1
    assert funnel["unused variable (hors cliquet)"] == 1


def test_a_mention_in_prose_does_not_make_a_function_alive() -> None:
    assert not any(s.endswith(".md") for s in dead_code.CORPUS_SUFFIXES)


def test_a_comment_or_a_docstring_is_not_a_caller() -> None:
    """The tool's first version was green on its own defect: its docstring named a dead
    function, and that word made it alive."""
    src = '"""Module doc: prose_only is cited here."""\n# and prose_only here\n' \
          'def prose_only():\n    """prose_only, in its own docstring."""\n'
    out = "src/p.py:3: unused function 'prose_only' (60% confidence)"
    _, live = dead_code.classify(dead_code.parse(out), {"src/p.py": src})
    assert [c.name for c in live] == ["prose_only"]
