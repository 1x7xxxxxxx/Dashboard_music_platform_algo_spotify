"""
Guard — a standalone script under `tools/` must still be able to start.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: tools/**
Persists in: nothing

Error class: tool-imports-the-app-without-a-path.

Measured 2026-08-23. Widening the credential-redaction guard to `tools/` added
`from src.utils.safe_error import safe_error` to six scripts. Five already put the repo
root on `sys.path`; two did not, and those two died at startup with
`ModuleNotFoundError: No module named 'src'`.

Python seeds `sys.path` with the SCRIPT's own directory, never the caller's cwd. So a
tool under `tools/` cannot import the app package however it is invoked — `cd repo &&
python3 tools/x.py` fails exactly like any other form. The two victims were
`tools/dev/check_manifest_consistency.py` (a CI gate: `audit_runner` read its exit 1 as
a manifest drift, pointing at the wrong class entirely) and `tools/notify_schema_drift.py`
(the 04h production drift cron — the alert itself, silenced by the import meant to
harden it).

This is the fourth time the SCOPE of a guard was the defect rather than its logic: the
files newly brought under the guard had a different runtime contract than the files it
was written against.
"""

import ast
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOLS = _REPO / "tools"


def _tool_scripts() -> list[str]:
    return sorted(
        str(p.relative_to(_REPO))
        for p in _TOOLS.rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _first_app_import_line(tree: ast.Module) -> int | None:
    """Line of the first top-level `import src…` / `from src… import …`, if any."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "src" or node.module.startswith("src.")):
                return node.lineno
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "src" or alias.name.startswith("src."):
                    return node.lineno
    return None


def _path_mutation_lines(tree: ast.Module) -> list[int]:
    """Lines of `sys.path.insert(...)` / `sys.path.append(...)`."""
    out: list[int] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"insert", "append", "extend"}
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "path"):
            out.append(node.lineno)
    return sorted(out)


def test_the_scope_is_not_empty() -> None:
    assert len(_tool_scripts()) > 10, "the tools/ walk found almost nothing"


@pytest.mark.parametrize("rel", _tool_scripts())
def test_a_tool_that_imports_the_app_puts_the_repo_root_on_the_path(rel: str) -> None:
    tree = ast.parse((_REPO / rel).read_text(encoding="utf-8"))
    import_line = _first_app_import_line(tree)
    if import_line is None:
        pytest.skip("does not import the app package")

    mutations = [ln for ln in _path_mutation_lines(tree) if ln < import_line]
    assert mutations, (
        f"{rel} imports the app package at line {import_line} with nothing adding the "
        f"repo root to sys.path before it. Python seeds sys.path with the SCRIPT's "
        f"directory, not the caller's cwd, so this script dies at startup with "
        f"ModuleNotFoundError however it is invoked. Add, above the import:\n"
        f"    sys.path.insert(0, str(Path(__file__).resolve().parents[N]))"
    )
