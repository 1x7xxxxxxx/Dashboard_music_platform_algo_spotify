"""Every module of src/ is reached by something — an import, a dotted string, an entry point (R630).

Type: Hook
Uses: tools/dev/unreached_modules.py
Persists in: nothing

Measured 2026-10-16: 16 `src/database/*_schema.py` were imported by nothing and pulled
the database layer's coverage to 50,4 % (86,1 % without them). `tests/test_dead_code_only_shrinks.py`
had a baseline of `[]` and did not see them: it reads functions, not modules. They were
archived; the baseline here is empty and stays empty.

guard_scope: a module of src/ that no import, dotted string, `pkgutil.iter_modules`
package or launch path reaches. NOT covered: a module only TESTS import (reached here —
`tools/dev/dead_code.py --without-tests` is that bucket), a path read as text by a test
(deliberately not a reach), a name built by concatenation.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("unreached_modules",
                                               ROOT / "tools" / "dev" / "unreached_modules.py")
um = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(um)


def test_every_src_module_is_reached() -> None:
    found = um.unreached()
    assert not found, ("modules of src/ that nothing imports, names or launches — archive "
                       f"them (archive/README.md) or wire them: {found}")


def test_the_detector_reads_each_kind_of_reach() -> None:
    names = {"src.a.imported", "views.dyn", "src.pkg.used.thing"}
    paths = {"src/a/launched.py"}
    prefixes = {"src.iter"}
    assert um._reached("src.a.imported", names, prefixes, paths)
    assert um._reached("src.dashboard.views.dyn", names, prefixes, paths)  # routes string
    assert um._reached("src.a.launched", names, prefixes, paths)           # run by path
    assert um._reached("src.iter.any", names, prefixes, paths)             # pkgutil package
    assert um._reached("src.pkg", names, prefixes, paths)                  # parent package
    # The neighbours that look reached and are not:
    assert not um._reached("src.a.orphan", names, prefixes, paths)
    assert not um._reached("src.b.dyn", {"dyn"}, set(), set()), "a one-word string is no reach"
    assert not um._reached("src.iter.sub.deep", names, prefixes, paths), \
        "iter_modules loads one level, not the grandchildren"


def test_relative_imports_resolve_to_the_module_they_name() -> None:
    node = ast.parse("from .sibling import x").body[0]
    assert um._resolve_from(node, "src/pkg/mod.py") == "src.pkg.sibling"
    assert um._resolve_from(node, "src/pkg/__init__.py") == "src.pkg.sibling"
    up = ast.parse("from ..other import y").body[0]
    assert um._resolve_from(up, "src/pkg/sub/mod.py") == "src.pkg.other"


def test_iter_modules_marks_the_package_it_walks() -> None:
    tree = ast.parse("from src.x import cat\nimport pkgutil\n"
                     "for m in pkgutil.iter_modules(cat.__path__): pass\n")
    assert um._iterated_packages(tree, {"cat": "src.x.cat"}) == {"src.x.cat"}
