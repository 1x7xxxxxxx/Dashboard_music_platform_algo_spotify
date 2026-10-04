#!/usr/bin/env python3
"""R361 — a governance file changed: run the tests that NAME it, before the commit leaves.

Type: Utility (dev)
Uses: git ls-files / git grep, the venv's pytest, tools/dev/pytest_workers.py
Triggers: the pre-commit hook `governance-readers` (staged names), `make roadmap-close`
Persists in: nothing

Why — measured on 2026-10-04 from the defect log (`make defect-log`)
--------------------------------------------------------------------
The nine `recurrence:` tickets of that day were ALL reds of main's CI on a governance
guard (roadmap index, requirement catalogue, docs). The last one: `make roadmap-close
ID=R356` left six requirements naming a closed line, and the closure printed two tests to
run — neither reads the catalogue. The full selection would have caught it, but it is
274 s in series for a roadmap-only change; the tests that NAME `checklist.md` are 31 s.

The predicate is the property « this test reads that file », approximated by the
file's path or — when no other tracked file shares it — its basename appearing in the
test's source (tests build paths as `ROOT / "roadmap" / "checklist.md"`). A test that
reaches the file only through a script it calls is NOT selected: that is this gate's
uncovered neighbour, and CI stays the net for it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / ".venv" / "bin" / "python"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=60).stdout


def needles(rel: str, tracked: list[str]) -> list[str]:
    """What a reader of `rel` writes in its source. Pure."""
    base = Path(rel).name
    shared = sum(1 for t in tracked if Path(t).name == base) > 1
    return [rel] if shared else [rel, base]


def readers(files: list[str]) -> list[str]:
    """Test files whose source names one of `files` (themselves excluded)."""
    tracked = _git("ls-files").split()
    out: set[str] = set()
    for rel in files:
        for n in needles(rel, tracked):
            out |= set(_git("grep", "-l", "-F", n, "--", "tests/test_*.py").split())
    return sorted(t for t in out if t not in files and (ROOT / t).is_file())


def _workers() -> str:
    try:
        return subprocess.run([str(PY), "tools/dev/pytest_workers.py"], cwd=ROOT,
                              capture_output=True, text=True, timeout=30).stdout.strip() or "2"
    except (OSError, subprocess.SubprocessError):
        return "2"


def main(argv: list[str]) -> int:
    files = [f for f in argv if f]
    tests = readers(files)
    if not tests:
        print(f"governance-readers : aucun test ne nomme {', '.join(files) or '(rien)'}")
        return 0
    if not PY.exists():
        print("❌ venv absent — make sync", file=sys.stderr)
        return 1
    print(f"governance-readers : {len(tests)} test(s) nomment {', '.join(files)}")
    rc = subprocess.run([str(PY), "-m", "pytest", "-q", "-p", "no:cacheprovider",
                         "-n", _workers(), *tests], cwd=ROOT).returncode
    if rc:
        print("❌ un test qui LIT ce fichier de pilotage est rouge — la CI de main le serait "
              "aussi (R361).", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
