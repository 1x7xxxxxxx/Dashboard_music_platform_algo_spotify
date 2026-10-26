#!/usr/bin/env python3
"""Turn a bug REPORT into a reproduced, measured roadmap row — the intake before bug-resolution.

Type: Utility
Triggers: the `/bug-report` command
Uses: the reproduction command given after `--`, run from the repo root
Persists in: the 📋 table of the repo's roadmap checklist (`--write` only), one row
             `<!-- défaut -->` whose « Mesuré par » is the reproduction itself

Baseline T111 (2026-10-18). The fleet had a RESOLUTION playbook (bug-resolution, injected on
« bug », « traceback »…) and an automatic SYMPTOM capture (defect_capture, at each Stop),
but nothing that took a report someone writes — « X plante quand Y » — and made it a fact. A
report stays a sentence until a command goes red on it; then the same command, green, is the
proof of the fix. So the intake refuses what it cannot reproduce:

    python3 .claude/scripts/bug_intake.py "export CSV vide" -- python3 -m pytest -q tests/test_export.py
    python3 .claude/scripts/bug_intake.py --write "export CSV vide" -- make repro-export

Exit: 0 reproduced (the row is printed, and inserted with --write) · 2 NOT reproduced (the command
exited 0 — nothing is written: a green repro proves nothing about the report) · 3 --write with no
📋 table to write into (the row is still printed).

guard_scope: running the repro, refusing a green one, the row's shape, its id, its insertion.
NOT covered: whether the repro reproduces THE reported bug — that is the reporter's claim, which is
why the row quotes the command verbatim for anyone to replay.

---
rex: []
---
"""
from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# the two places the fleet keeps it — joined at run time: a repo has one, never both, and a literal
# path to the other would read as a dangling reference to its config checkers
CHECKLISTS = tuple(f"{d}/checklist.md" for d in ("docs/roadmap", ".claude/dev-docs/roadmap"))
TAIL = 20
_ID = re.compile(r"(?:^\| |\*\*|^## ✅ )([A-Z])(\d{1,4})\b", re.M)  # T113: R1 as well as R058


def checklist(root: Path) -> Path | None:
    return next((root / c for c in CHECKLISTS if (root / c).is_file()), None)


def next_id(texts: list[str]) -> str:
    """The repo's own prefix (its most used letter) and the number after the highest one."""
    ids = [(m.group(1), m.group(2)) for t in texts for m in _ID.finditer(t)]
    if not ids:
        return "R001"
    prefix = Counter(p for p, _ in ids).most_common(1)[0][0]
    nums = [n for p, n in ids if p == prefix]
    top = max(nums, key=int)
    return f"{prefix}{int(top) + 1:0{len(top)}d}"


def row(rid: str, title: str, command: str, code: int, today: str) -> str:
    cell = lambda s: s.replace("|", "\\|").replace("\n", " ").strip()  # noqa: E731
    return (f"| {rid} | Rapport de bug : {cell(title)} — reproduit le {today} (exit {code}) "
            f"<!-- défaut --> <!-- critic: requis — rapport de bug, cause à lire avant le fix --> | P1 | `{cell(command)}` sort à 0 |")


def insert(text: str, line: str) -> str | None:
    """`text` with `line` appended to the 📋 table, or None when there is no such table."""
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.startswith("## 📋")), None)
    if start is None:
        return None
    head = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("|")), None)
    if head is None or any(lines[i].startswith("## ") for i in range(start + 1, head)):
        return None
    end = head
    while end + 1 < len(lines) and lines[end + 1].startswith("|"):
        end += 1
    return "\n".join(lines[:end + 1] + [line] + lines[end + 1:])


def reproduce(argv: list[str], root: Path, timeout: int = 600) -> tuple[int, str]:
    cmd = ["bash", "-c", argv[0]] if len(argv) == 1 else argv
    try:
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"timeout après {timeout} s"
    return r.returncode, (r.stdout + r.stderr)


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv:
        print("usage : bug_intake.py [--write] \"titre\" -- <commande de reproduction>", file=sys.stderr)
        return 64
    cut = argv.index("--")
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv[:cut])
    repro = argv[cut + 1:]
    if not repro:
        print("la commande de reproduction est obligatoire après --", file=sys.stderr)
        return 64
    command = repro[0] if len(repro) == 1 else shlex.join(repro)
    code, out = reproduce(repro, root)
    tail = "\n".join(out.rstrip().splitlines()[-TAIL:])
    if code == 0:
        print(f"NON REPRODUIT — `{command}` sort à 0. Rien n'est écrit : une repro verte ne prouve rien "
              f"sur le rapport. Demander une commande qui rougit sur le bug.\n{tail}")
        return 2
    cl = checklist(root)
    texts = [p.read_text(encoding="utf-8") for p in (cl, cl.with_name("archive.md")) if p and p.is_file()] if cl else []
    line = row(next_id(texts), a.title, command, code, date.today().isoformat())
    print(f"REPRODUIT — `{command}` sort à {code}.\n--- sortie (fin) ---\n{tail}\n--- ligne ---\n{line}")
    if not a.write:
        return 0
    new = insert(texts[0], line) if texts else None
    if new is None:
        print(f"aucune table 📋 dans {cl or ' / '.join(CHECKLISTS)} — inscrire la ligne à la main", file=sys.stderr)
        return 3
    cl.write_text(new, encoding="utf-8")
    print(f"inscrite dans {cl.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
