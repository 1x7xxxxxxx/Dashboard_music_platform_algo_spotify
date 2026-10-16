#!/usr/bin/env python3
"""Modules of src/ that nothing reaches — no import, no dotted string, no entry point.

Type: Utility
Uses: git ls-files, ast
Triggers: tests/test_every_src_module_is_reached.py ; by hand — `python3 tools/dev/unreached_modules.py`
Persists in: nothing (stdout)

Why this exists — measured 2026-10-16 (R620 → R630)
---------------------------------------------------
Per-layer coverage put `src/database` at 50,4 %. The cause was not a test gap: 16
`*_schema.py` modules (dicts of CREATE TABLE strings, every table also in init_db.sql or
migrations/) were imported by NOTHING, at 0 %, 236 lines. `tools/dev/dead_code.py` had
a baseline of `[]` and did not see them: it reads FUNCTIONS by name, and a module that
nobody imports still has functions that its own `__main__` or a docstring names.

What counts as reaching a module `src.a.b`
------------------------------------------
* an `import` / `from … import` in tracked Python outside archive/ (tests included — a
  module only tests import is a different bucket, see `dead_code.py --without-tests`);
* a string literal that IS a dotted name ending in `a.b` with ≥2 components
  (`importlib.import_module("views.x")`, routes.py, `-m src.a.b`);
* `pkgutil.iter_modules(<pkg>.__path__)` — every submodule of that package;
* a path `src/a/b.py` written in Python OUTSIDE tests/, or in a Makefile, Dockerfile,
  shell script or YAML — a script launched by its path.

guard_scope — what it does NOT see: a path read as TEXT by a test is deliberately not a
reach (a test parsing a file does not run it — the apple schema test did exactly that);
a module name built by concatenation other than an f-string prefix handled by pkgutil; a
one-word dotted string (`"common"`) is ignored, so a module run by `sys.path` hacks under
a one-word name is reported as unreached (none on 2026-10-16).
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_TEXT_GLOBS = ("Makefile", "*Dockerfile*", "*.sh", "*.yml", "*.yaml", "*.toml", "*.cfg")
_PATH = re.compile(r"src/[\w/]+\.py")
_DOTTED = re.compile(r"[A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)+")


def _tracked(*globs: str) -> list[str]:
    out = subprocess.run(["git", "ls-files", *globs], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.split()
    return [f for f in out if not f.startswith("archive/") and (ROOT / f).is_file()]


def module_name(path: str) -> str:
    dotted = path[:-3].replace("/", ".")
    return dotted.removesuffix(".__init__")


def _resolve_from(node: ast.ImportFrom, here: str) -> str:
    if not node.level:
        return node.module or ""
    parts = module_name(here).split(".")
    if not here.endswith("__init__.py"):
        parts = parts[:-1]
    parts = parts[: len(parts) - node.level + 1]
    return ".".join(parts + ([node.module] if node.module else []))


def _iterated_packages(tree: ast.AST, aliases: dict[str, str]) -> set[str]:
    """`pkgutil.iter_modules(pkg.__path__)` → the package whose submodules all load."""
    found = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "iter_modules"
                and node.args and isinstance(node.args[0], ast.Attribute)
                and node.args[0].attr == "__path__"
                and isinstance(node.args[0].value, ast.Name)):
            name = node.args[0].value.id
            found.add(aliases.get(name, name))
    return found


def _scan_python(path: str, names: set[str], prefixes: set[str], paths: set[str]) -> None:
    text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name)
                aliases[a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_from(node, path)
            names.add(base)
            for a in node.names:
                names.add(f"{base}.{a.name}")
                aliases[a.asname or a.name] = f"{base}.{a.name}"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _DOTTED.fullmatch(node.value):
                names.add(node.value)
            if not path.startswith("tests/"):
                paths.update(_PATH.findall(node.value))
        elif isinstance(node, ast.JoinedStr):  # f"src.x.views.{name}" → a prefix
            head = node.values[0] if node.values else None
            if isinstance(head, ast.Constant) and str(head.value).endswith("."):
                prefixes.add(str(head.value).rstrip("."))
    prefixes.update(_iterated_packages(tree, aliases))


def _reached(mod: str, names: set[str], prefixes: set[str], paths: set[str]) -> bool:
    if mod.replace(".", "/") + ".py" in paths or mod.replace(".", "/") + "/__init__.py" in paths:
        return True
    parts = mod.split(".")
    if any(".".join(parts[i:]) in names for i in range(len(parts) - 1)):
        return True
    if any(n.startswith(mod + ".") for n in names):
        return True  # a package is reached when one of its submodules is
    return ".".join(parts[:-1]) in prefixes


def unreached() -> list[str]:
    names: set[str] = set()
    prefixes: set[str] = set()
    paths: set[str] = set()
    for f in _tracked("*.py"):
        _scan_python(f, names, prefixes, paths)
    for f in _tracked(*_TEXT_GLOBS):
        text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
        paths.update(_PATH.findall(text))
        names.update(re.findall(r"-m\s+([\w.]+)", text))
    return [f for f in _tracked("src/*.py")
            if not _reached(module_name(f), names, prefixes, paths)]


def main() -> int:
    found = unreached()
    for f in found:
        print(f)
    print(f"{len(found)} module(s) of src/ reached by nothing", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
