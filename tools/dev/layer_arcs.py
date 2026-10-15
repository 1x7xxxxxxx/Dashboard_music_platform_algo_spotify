#!/usr/bin/env python3
"""Upward import arcs between the layers of src/: a low layer importing an app, or an app another.

Type: Utility
Uses: ast, git ls-files (src/ and airflow/dags/)
Triggers: tests/test_layer_arcs_only_shrink.py (the ratchet) ; by hand —
          `python3 tools/dev/layer_arcs.py [--json]`
Persists in: nothing (stdout) — the baseline is tests/layer_arcs_baseline.json (BASELINE)

Why this exists — measured 2026-10-15 (R616)
--------------------------------------------
The layers of src/ are two apps (`api`, `dashboard`) over shared code (`collectors`,
`transformers`, `database`, `models`, `utils`). Nothing enforced the direction: 8 arcs
went UP — 7 from `src/utils` into the dashboard (6 inside a function, imported lazily),
and `src/api/deps.py` importing `src.dashboard.utils` at module level, so the API's
import pulls the dashboard's door. None was justified; moving the misplaced modules is
its own roadmap line. This tool counts them; the ratchet lets the count only fall.

An arc is read STRUCTURALLY, from `import` and `from … import` nodes — never from text:
the `Uses:` docstrings of these very files name `src.dashboard.*`. Its key is
`file::target module`, where `from src.dashboard.utils import i18n` resolves to the
submodule `src.dashboard.utils.i18n` (a key on the package would absorb every new import
from it), and `from src import dashboard` to `src.dashboard`. Its VALUE is the level:
`module` (runs at import — a cost and a cycle risk, `TYPE_CHECKING` and `try` included)
or `local` (inside a function).

Since R626 the DAGs are scanned too: `airflow/dags/` is the layer `dags`, above the
shared code and below the apps — a DAG importing `src.dashboard` or `src.api` is an arc.
Each baseline entry is `{"level": …, "reason": …}`: an arc that stays says why, in
writing, or the ratchet is red.

What this tool does NOT see (guard_scope)
-----------------------------------------
* `importlib.import_module("src.dashboard…")` or `__import__` with a string — 0 crossing a
  layer on 2026-10-15 (the two in src/dashboard stay inside it).
* Imports from `tools/`, `tests/` or scripts — they may reach any layer.
* Imports between low layers (`database` → `collectors`, …): no direction is declared
  among them.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tests" / "layer_arcs_baseline.json"
LOW = frozenset({"collectors", "transformers", "database", "models", "utils"})
APPS = frozenset({"api", "dashboard"})


def is_upward(source_layer: str, target_layer: str) -> bool:
    if source_layer == target_layer:
        return False
    return target_layer in APPS and (source_layer in LOW | APPS | {"dags"})


def _is_module(root: Path, dotted: str) -> bool:
    p = root.joinpath(*dotted.split("."))
    return p.with_suffix(".py").is_file() or (p / "__init__.py").is_file()


def targets(node: ast.AST, root: Path) -> list[str]:
    """The `src.…` modules an import node names, each resolved to its submodule."""
    if isinstance(node, ast.Import):
        return [a.name for a in node.names if a.name.startswith("src.")]
    if not (isinstance(node, ast.ImportFrom) and node.level == 0 and node.module):
        return []
    if node.module != "src" and not node.module.startswith("src."):
        return []
    out = []
    for a in node.names:
        sub = f"{node.module}.{a.name}"
        out.append(sub if a.name != "*" and _is_module(root, sub) else node.module)
    return [t for t in out if t != "src"]


def _local_nodes(tree: ast.AST) -> set[int]:
    """ids of the import nodes that sit inside a function (run on call, not on import)."""
    inside = set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            inside |= {id(n) for n in ast.walk(fn) if isinstance(n, (ast.Import, ast.ImportFrom))}
    return inside


def layer_of(path: str) -> str | None:
    """`src/<layer>/…` → `<layer>` ; `airflow/dags/…` → `dags` ; anything else → None."""
    parts = Path(path).parts
    if len(parts) >= 3 and parts[0] == "src":
        return parts[1]
    if len(parts) >= 3 and parts[:2] == ("airflow", "dags"):
        return "dags"
    return None


def arcs_of(path: str, source: str, root: Path = ROOT) -> dict[str, str]:
    """{`path::target`: `module`|`local`} for the upward arcs of one file (src/ or a DAG)."""
    layer = layer_of(path)
    if layer is None:
        return {}
    tree = ast.parse(source)
    local = _local_nodes(tree)
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        for tgt in targets(node, root):
            if not is_upward(layer, tgt.split(".")[1]):
                continue
            key, level = f"{path}::{tgt}", "local" if id(node) in local else "module"
            out[key] = "module" if out.get(key) == "module" else level
    return out


def current() -> dict[str, str]:
    files = subprocess.run(["git", "ls-files", "src/*.py", "airflow/dags/*.py"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    out: dict[str, str] = {}
    for f in files:
        if (ROOT / f).is_file():
            out.update(arcs_of(f, (ROOT / f).read_text(encoding="utf-8")))
    return out


def load_baseline() -> dict[str, dict[str, str]]:
    """{key: {"level": `module`|`local`, "reason": why this arc stays}}."""
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="the arcs, as the baseline stores them")
    a = ap.parse_args(argv)
    arcs = current()
    if a.json:
        print(json.dumps(dict(sorted(arcs.items())), indent=1, ensure_ascii=False))
        return 0
    for key, level in sorted(arcs.items()):
        print(f"{level:6} {key}")
    print(f"{len(arcs)} upward arc(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
