#!/usr/bin/env python3
"""PreToolUse (Edit|Write|MultiEdit|NotebookEdit|Bash): no product-code edit while no action is open.

Type: Hook
Uses: tools/dev/require_roadmap_id.py (open_ids, next_id, is_product)
Triggers: every file edit; acts only on `src/`, `airflow/dags/`, `migrations/`
Persists in: nothing

R196 (2026-09-26), owner: « comment peut-on se garantir d'inscrire une action en roadmap
avant de l'exécuter ? » — answered « avant d'écrire le code ». This is the BEFORE half: the
first product-code edit is refused while the index table of the roadmap has no open row, and
the refusal names the next free id and the gesture. The commit half
(`tools/dev/require_roadmap_id.py`, git commit-msg + CI) binds each commit to an open id.

Why this is not the hook code-critic rejected on 2026-09-25 (see archive/claude-config/hooks/draft_roadmap.py): that one
fired on a line the model must first write, so it never saw the action the model FORGOT.
This one fires on the gesture itself — editing product code — which cannot be forgotten.

Limits, said rather than hidden:
  * it checks that SOME action is open, not that this edit belongs to it — with several open
    rows (the common case in a long session) any edit passes; the commit half binds the id;
  * a Bash command is judged by the files it writes with `>`, `>>`, `>|` or `tee` (heredoc
    bodies excluded) — added 2026-10-16 from the governance preset, measured there on 49 216
    Bash commands: 0 parse failure, ~980 writing `tests/` or `src/` by redirection. `sed -i`,
    `cp`, `mv` and a script that writes are still unseen; the commit half and the CI catch them.

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
import re
import shlex
import subprocess
import sys
from pathlib import Path
import sys as _sys  # R365 — one trace line per run, even for a silent hook
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "hooks"))
from _hook_trace import trace as _trace  # noqa: E402
_trace(__file__)

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


_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")


def bash_targets(command: str) -> list[str]:
    """Files a Bash command writes by `>`, `>>`, `>|` or `tee` — heredoc bodies excluded."""
    kept, end = [], None
    for line in command.splitlines():
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        kept.append(line)
        m = _HEREDOC.search(line)
        if m:
            end = m.group(2)
    lex = shlex.shlex("\n".join(kept), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:
        return []
    out, tee = [], False
    for i, tok in enumerate(tokens):
        if tok in (">", ">>", ">|") and i + 1 < len(tokens):
            out.append(tokens[i + 1])
        elif tok == "tee":
            tee = True
        elif tee and set(tok) <= set("|&;<>()"):
            tee = False
        elif tee and not tok.startswith("-"):
            out.append(tok)
    # `$VAR/x` is unknowable before the shell expands it: not judged (fail open).
    return [os.path.expanduser(t) for t in out
            if not t.startswith(("&", "/dev/")) and not t.isdigit() and "$" not in t]


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_input = event.get("tool_input") or {}
    cwd = event.get("cwd") or os.getcwd()
    if event.get("tool_name") == "Bash":
        targets = bash_targets(tool_input.get("command") or "")
    else:
        targets = [tool_input.get("file_path") or tool_input.get("notebook_path") or ""]
    for target in filter(None, targets):
        message = refusal(target, cwd)
        if message:
            print(message, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
