#!/usr/bin/env python3
"""PreToolUse (Edit|Write|MultiEdit|NotebookEdit): no product-code edit while no action is open.

Type: Hook
Uses: tools/dev/require_roadmap_id.py (open_ids, next_id, is_product)
Triggers: every file edit; acts only on `src/`, `airflow/dags/`, `migrations/`
Persists in: nothing

R196 (2026-09-26), owner: « comment peut-on se garantir d'inscrire une action en roadmap
avant de l'exécuter ? » — answered « avant d'écrire le code ». This is the BEFORE half: the
first product-code edit is refused while the index table of the roadmap has no open row, and
the refusal names the next free id and the gesture. The commit half
(`tools/dev/require_roadmap_id.py`, git commit-msg + CI) binds each commit to an open id.

Why this is not the hook code-critic rejected on 2026-09-25 (see .claude/.retired/hooks/draft_roadmap.py): that one
fired on a line the model must first write, so it never saw the action the model FORGOT.
This one fires on the gesture itself — editing product code — which cannot be forgotten.

Limits, said rather than hidden:
  * it checks that SOME action is open, not that this edit belongs to it — with several open
    rows (the common case in a long session) any edit passes; the commit half binds the id;
  * an edit made through Bash (`sed -i`, a script) never reaches this hook; the commit half
    and the CI catch it later.

The checklist read is the one of the EDITED FILE's repository (`git rev-parse` from its
directory), so an engineering-loop worktree is judged by its own copy (code-critic).
---
rex: []
---
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_TOOL = Path(__file__).resolve().parents[2] / "tools" / "dev" / "require_roadmap_id.py"


def _gate():
    spec = importlib.util.spec_from_file_location("require_roadmap_id", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _repo_root(path: Path) -> Path | None:
    d = path.parent
    while not d.exists() and d != d.parent:
        d = d.parent
    out = subprocess.run(["git", "-C", str(d), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    return Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None


def refusal(target: str, cwd: str) -> str | None:
    """The message to block with, or None. Reads the repository of `target`."""
    gate = _gate()
    path = Path(target) if os.path.isabs(target) else Path(cwd) / target
    root = _repo_root(path)
    if root is None:
        return None
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    if not gate.is_product(rel):
        return None

    def read(p: str) -> str:
        f = root / p
        return f.read_text(encoding="utf-8") if f.exists() else ""

    checklist = read(gate.CHECKLIST)
    if gate.open_ids(checklist):
        return None
    nid = gate.next_id(checklist, read(gate.ARCHIVE))
    return (f"🚫 R196 — aucune action ouverte dans la roadmap : `{rel}` ne se modifie pas "
            "avant qu'elle y soit inscrite.\n"
            f"   1. ajoute `| {nid} | <l'action demandée> | P3 | <comment on la mesure> |` "
            f"à l'index « 📋 Tâches ouvertes » de {gate.CHECKLIST}\n"
            f"   2. commite la roadmap : « Roadmap : {nid} inscrite »\n"
            f"   3. recommence la modification, puis commite le code avec « {nid} : … ».")


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_input = event.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        return 0
    message = refusal(target, event.get("cwd") or os.getcwd())
    if message:
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
