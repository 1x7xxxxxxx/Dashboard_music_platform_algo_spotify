"""R447 — an import written inside a script string is an edge of the selector's graph.

Type: Sub
Uses: .claude/scripts/select_tests.py (select, imports_in_strings)
Triggers: pytest
Persists in: nothing

`test_a_view_says_something_or_says_why.py` renders every view through
`AppTest.from_string("from src.dashboard.views.{view} import show …")`. No `import`
statement names a view, so on 2026-10-05 a change to `revenue_forecast.py` did not
select it, `make test-changed` was green, and main went red in CI. Found by replaying
the selector on every CI red of main (R446).
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.xdist_group("the-selector-selects-what-changed")

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "select_tests_r447", REPO / ".claude" / "scripts" / "select_tests.py")
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)


def _repo(tmp_path: Path, test_body: str) -> Path:
    (tmp_path / "pkg" / "views").mkdir(parents=True)
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "views" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "views" / "page.py").write_text("def show():\n    return 1\n")
    (tmp_path / "pkg" / "other.py").write_text("X = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_render.py").write_text(test_body)
    (tmp_path / "tests" / "test_other.py").write_text(
        "from pkg.other import X\n\ndef test_x():\n    assert X\n")
    return tmp_path


def _picked(root: Path, changed: str) -> list[str]:
    return st.select(root, _changed=[changed])["paths"]


def test_a_templated_import_selects_the_test_for_any_module_under_it(tmp_path):
    root = _repo(tmp_path, (
        'SCRIPT = "from pkg.views.{view} import show\\nshow()"\n\n'
        "def test_render():\n    assert SCRIPT.format(view='page')\n"))
    assert "tests/test_render.py" in _picked(root, "pkg/views/page.py")
    assert "tests/test_render.py" not in _picked(root, "pkg/other.py")


def test_a_plain_import_in_a_string_selects_its_test(tmp_path):
    root = _repo(tmp_path, (
        'CODE = "import pkg.views.page; pkg.views.page.show()"\n\n'
        "def test_run():\n    assert CODE\n"))
    assert "tests/test_render.py" in _picked(root, "pkg/views/page.py")


def test_the_parser_reads_templates_fstring_pieces_and_ignores_prose():
    tree = ast.parse(
        'A = "from src.views.{v} import show"\n'
        'B = f"from src.views.{v} import show"\n'
        'C = "from src.utils.x import a, b"\n'
        'D = "import errors from the upload are shown"\n'
        'E = "import api.routers.kpis, api.routers.ml; print(1)"\n')
    names, prefixes = st.imports_in_strings(tree)
    assert prefixes == {"src.views"}
    assert {"src.utils.x", "src.utils.x.a", "src.utils.x.b"} <= names
    assert {"api.routers.kpis", "api.routers.ml"} <= names
    # prose yields names that resolve to no module of the repo — harmless, but no prefix
    assert "the" in names and "src.utils" not in prefixes


# R494 — `from pkg.views import page as p` captured `page as p` as the imported name;
# `pkg.views.page as p` resolved to nothing and fell back to the PACKAGE `pkg.views`.
# The body below deliberately never spells the file name nor the views directory: the
# mention rule rescued the real case (`test_new_guards_are_mutated_every_night.py`
# says "soundcloud.py" literally), and that rescue is exactly what hid the defect.
def test_an_aliased_import_in_a_string_selects_its_test(tmp_path):
    body = ('CODE = "from pkg.views import page as p"\n\n'
            "def test_run():\n    assert CODE\n")
    root = _repo(tmp_path, body)
    assert "page.py" not in body and "views/" not in body, "the guard must not be rescued"
    assert "tests/test_render.py" in _picked(root, "pkg/views/page.py")


def test_an_alias_or_a_parenthesis_does_not_corrupt_the_imported_name():
    names, _ = st.imports_in_strings(ast.parse('A = "from src.a import b as c, d"'))
    assert {n for n in names if n != "src.a"} == {"src.a.b", "src.a.d"}, names
    names, _ = st.imports_in_strings(ast.parse(
        'A = "from src.a import (b,  # note\\n c as k,)"'))
    assert {n for n in names if n != "src.a"} == {"src.a.b", "src.a.c"}, names
    names, _ = st.imports_in_strings(ast.parse('A = "import a.b as c, d as e"'))
    assert {"a.b", "d"} <= names, names
    for n in names:
        assert " " not in n and "(" not in n, n
