#!/usr/bin/env python3
"""No product-code commit without an OPEN roadmap line written BEFORE it (R196).

Type: Hook
Uses: git, .claude/dev-docs/roadmap/checklist.md (the `## 📋 Tâches ouvertes` table)
Triggers: git `commit-msg` (via .pre-commit-config.yaml) and `--range` in ci.yml
Persists in: nothing

Why this exists
---------------
Owner, 2026-09-26: « comment peut-on se garantir d'inscrire une action en roadmap avant de
l'exécuter ? ». Measured over the 118 product-code commits since 2026-09-12: 41 cited no
roadmap id, 15 wrote their id in the SAME commit as the code — after the fact. Every
existing mechanism only reminded (`check_roadmap_update.py`) or suggested
(`draft_roadmap.py`); a note does not hold a reflex, a gate does.

The rule, for a commit that touches product code (`src/`, `airflow/dags/`, `migrations/`):
its message cites >= 1 `Rnnn` that is an OPEN row of the index table in the PARENT commit —
i.e. written and committed before the work. An ARCHIVED id does not count (code-critic,
2026-09-26): the index is routinely driven to 0 open rows, so an archived id would always be
at hand to launder unrelated work. Merges and reverts are exempt — their messages are
generated, and refusing them would teach `--no-verify`.

What it does NOT prove: that the diff IS the cited task. With several open rows, any of them
passes. It binds a commit to an inscribed action, not a diff to its meaning.

The pre-edit half is `.claude/hooks/require_roadmap_entry.py` (PreToolUse), which uses the
functions below.

Usage:
  require_roadmap_id.py <commit-msg-file>        # git commit-msg hook (staged files)
  require_roadmap_id.py --range <A>..<B>          # CI: every commit of a push
---
rex: []
---
"""
from __future__ import annotations

import re
import subprocess
import sys

CHECKLIST = ".claude/dev-docs/roadmap/checklist.md"
ARCHIVE = ".claude/dev-docs/roadmap/archive.md"
PRODUCT_PREFIXES = ("src/", "airflow/dags/", "migrations/")
INDEX_TITLE = "## 📋 Tâches ouvertes"
_ROW = re.compile(r"^\|\s*(R\d+)\s*\|")
_CITED = re.compile(r"\bR(\d{1,4})\b")
_ANY_ID = re.compile(r"\bR(\d{1,4})\b")
# The gate judges only commits made once it existed: a parent without this file predates it.
_SELF = "tools/dev/require_roadmap_id.py"


def is_product(path: str) -> bool:
    return path.startswith(PRODUCT_PREFIXES)


def open_ids(checklist: str) -> set[str]:
    """The `Rnnn` rows of the FIRST table under the open-tasks title — structure, not text:
    an id cited in prose, a comment or another table is not an open row."""
    ids: set[str] = set()
    lines = checklist.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith(INDEX_TITLE))
    except StopIteration:
        return ids
    in_table = False
    for ln in lines[start + 1:]:
        if ln.startswith("## "):
            break
        if ln.startswith("|"):
            in_table = True
            m = _ROW.match(ln)
            if m:
                ids.add(m.group(1))
        elif in_table:
            break
    return ids


def next_id(*texts: str) -> str:
    nums = [int(n) for t in texts for n in _ANY_ID.findall(t)]
    return f"R{max(nums, default=0) + 1}"


def cited(message: str) -> set[str]:
    body = "\n".join(ln for ln in message.splitlines() if not ln.startswith("#"))
    return {f"R{n}" for n in _CITED.findall(body)}


def is_exempt(message: str, parents: int) -> bool:
    first = message.strip().splitlines()[0] if message.strip() else ""
    return parents > 1 or first.startswith(("Revert \"", "Merge "))


def verdict(files: list[str], message: str, parent_checklist: str,
            parents: int = 1) -> str | None:
    """None when the commit may go; otherwise the reason. Pure."""
    if is_exempt(message, parents) or not any(is_product(f) for f in files):
        return None
    ids = cited(message)
    open_before = open_ids(parent_checklist)
    if not ids:
        return "le message ne cite aucun Rnnn"
    if not ids & open_before:
        return (f"{', '.join(sorted(ids))} n'est pas une ligne OUVERTE de l'index dans le "
                "commit précédent (une ligne archivée ne compte pas)")
    return None


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def _show(rev: str, path: str) -> str:
    return _git("show", f"{rev}:{path}")


def _gesture(reason: str) -> str:
    nid = next_id(_show("HEAD", CHECKLIST), _show("HEAD", ARCHIVE))
    return (f"🚫 R196 — commit de code produit refusé : {reason}.\n"
            "   Une action entre dans la roadmap AVANT d'être exécutée :\n"
            f"     1. ajoute `| {nid} | <l'action> | P3 | <comment on la mesure> |` à l'index "
            f"« {INDEX_TITLE[3:]} » de {CHECKLIST}\n"
            f"     2. git commit {CHECKLIST} -m \"Roadmap : {nid} inscrite\"\n"
            f"     3. recommite le code avec « {nid} : … » dans le message.")


def check_staged(msg_file: str) -> int:
    message = open(msg_file, encoding="utf-8").read()
    files = _git("diff", "--cached", "--name-only").split()
    merging = bool(_git("rev-parse", "-q", "--verify", "MERGE_HEAD").strip())
    reason = verdict(files, message, _show("HEAD", CHECKLIST), 2 if merging else 1)
    if reason:
        print(_gesture(reason), file=sys.stderr)
        return 1
    return 0


def check_range(rng: str) -> int:
    bad = []
    for sha in _git("rev-list", "--reverse", rng).split():
        parents = _git("rev-list", "--parents", "-n", "1", sha).split()[1:]
        if not parents or not _show(parents[0], _SELF):
            continue  # the gate did not exist yet in the parent: not judged
        files = _git("diff-tree", "--no-commit-id", "--name-only", "-r", sha).split()
        message = _git("log", "-1", "--format=%B", sha)
        reason = verdict(files, message, _show(parents[0], CHECKLIST), len(parents))
        if reason:
            bad.append(f"  {sha[:7]} {message.splitlines()[0][:70]} — {reason}")
    if bad:
        print("🚫 R196 — commit(s) de code produit sans ligne de roadmap ouverte AVANT :",
              *bad, sep="\n", file=sys.stderr)
        return 1
    print(f"✅ R196 : chaque commit de code produit de {rng} cite une ligne ouverte avant lui")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--range":
        return check_range(argv[2])
    if len(argv) == 2:
        return check_staged(argv[1])
    print(__doc__.split("Usage:")[1].split("---")[0], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
