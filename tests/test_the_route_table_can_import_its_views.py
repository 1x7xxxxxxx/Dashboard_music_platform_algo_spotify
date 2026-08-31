"""`app.py` must guarantee the path its own 44 routes import from.

On 2026-08-30 22:34 a local instance mailed the admin:

    ModuleNotFoundError: No module named 'views'
      app.py:548 in _render_page
        elif page == "credentials": from views.credentials import show; show()

`app.py` inserted the REPO ROOT into `sys.path` (for `src.*`) but never its own
directory (for `views.*`). That entry arrived only as a side effect of Streamlit's
bootstrap — `sys.path.insert(0, dirname(abspath(main_script_path)))` — so every
route in the table depended on a third-party implementation detail the file never
asserted. Under `streamlit run` it works; under any other launcher the app boots
clean and dies on the FIRST navigation, because the routes are imported lazily.

Two things are pinned, and neither reads the file as text:

  * the guarantee itself, read out of the AST — a comment naming `views` or a
    docstring explaining the fix cannot satisfy it;
  * that every module the route table names actually exists, so a renamed view
    fails here instead of in a click.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_APP = _ROOT / "src" / "dashboard" / "app.py"
_VIEWS_DIR = _ROOT / "src" / "dashboard" / "views"


def _tree() -> ast.Module:
    return ast.parse(_APP.read_text(encoding="utf-8"))


def _parent_depth(node: ast.AST) -> int | None:
    """Depth of a `Path(__file__).resolve().parent.parent…` chain, else None."""
    depth = 0
    while isinstance(node, ast.Attribute):
        if node.attr != "parent":
            break
        depth += 1
        node = node.value
    # unwrap the .resolve() call at the base of the chain
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == "resolve":
        node = node.func.value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id == "Path":
        args = node.args
        if args and isinstance(args[0], ast.Name) and args[0].id == "__file__":
            return depth
    return None


def _path_insert_depths() -> set[int]:
    """`.parent` depths of every module-level path added to sys.path."""
    tree = _tree()
    bound: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            value = node.value
            # tolerate the str(...) wrapper the file uses
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) \
                    and value.func.id == "str" and value.args:
                value = value.args[0]
            depth = _parent_depth(value)
            if depth is not None:
                bound[node.targets[0].id] = depth

    inserted: set[int] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "insert":
            continue
        target = node.func.value
        if not (isinstance(target, ast.Attribute) and target.attr == "path"
                and isinstance(target.value, ast.Name) and target.value.id == "sys"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Name) and arg.id in bound:
                inserted.add(bound[arg.id])
    return inserted


def test_app_guarantees_its_own_directory_on_sys_path():
    """Depth 1 == src/dashboard, the package root the `views.*` routes need."""
    depths = _path_insert_depths()

    assert 3 in depths, (
        "app.py must keep inserting the repository root (Path(__file__).resolve()"
        ".parent.parent.parent) — `src.*` imports depend on it. Found depths: "
        f"{sorted(depths)}"
    )
    assert 1 in depths, (
        "app.py must insert its OWN directory (Path(__file__).resolve().parent) so "
        "the `from views.<page> import show` routes resolve under any launcher, not "
        "only under Streamlit's bootstrap. Found depths: "
        f"{sorted(depths)}. This is the 2026-08-30 ModuleNotFoundError verbatim."
    )


def test_every_routed_view_module_exists():
    """A route may not name a module that is not on disk."""
    routed = {
        node.module.split(".", 1)[1]
        for node in ast.walk(_tree())
        if isinstance(node, ast.ImportFrom)
        and node.module and node.module.startswith("views.")
    }

    assert routed, "no `from views.<page> import` route found — parser is blind"

    missing = sorted(m for m in routed if not (_VIEWS_DIR / f"{m}.py").exists()
                     and not (_VIEWS_DIR / m / "__init__.py").exists())
    assert not missing, (
        f"the route table imports view module(s) that do not exist: {missing}. "
        f"A lazy route fails on the click, never at boot."
    )
