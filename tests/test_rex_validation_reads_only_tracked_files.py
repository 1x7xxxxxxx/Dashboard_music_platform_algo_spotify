"""R359 — `validate_rex.py` judges the tree CI sees: an untracked file changes nothing.

Type: Test
Uses: .claude/scripts/validate_rex.py (run as a subprocess on a temporary `.claude/`)
Depends on: git (init / add) — no live service
Persists in: nothing

The scenario (2026-10-04): another session's UNTRACKED agent file had no `rex:` key, and the
`validate-rex` pre-commit hook (`--strict`) blocked a commit that did not touch it. CI, which
only sees committed files, would never have seen it. What must hold:
1. inside a git work tree, an untracked tool without `rex:` and an untracked malformed
   archive do not change the verdict;
2. the same file, once staged, IS judged — the filter is "visible to git", not "ignored";
3. outside a work tree the validator still reads the disk (fallback, never silent).

Mutation record (2026-10-04): seen red with the `visible` filter removed from `_iter_files`
(test 1 red), and with `_git_visible` returning `set()` instead of None on a non-repo
(test 3 red).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / ".claude" / "scripts" / "validate_rex.py"
GOOD = "---\nname: ok\nrex: []\n---\nbody\n"
NO_REX = "---\nname: stray\n---\nbody\n"
BAD_ARCHIVE = "---\nrex:\n  - date: 2026-10\n    issue: x\n---\n"


def _run(claude: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(VALIDATOR), "--strict", "--root", str(claude)],
                          capture_output=True, text=True, timeout=60)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _tree(base: Path) -> Path:
    agents = base / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "ok.md").write_text(GOOD)
    return base / ".claude"


def test_an_untracked_file_does_not_change_the_verdict(tmp_path: Path) -> None:
    claude = _tree(tmp_path)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    (claude / "agents" / "stray.md").write_text(NO_REX)
    (claude / "agents" / "stray.rex.md").write_text(BAD_ARCHIVE)
    res = _run(claude)
    assert res.returncode == 0, res.stdout + res.stderr


def test_a_staged_file_is_judged(tmp_path: Path) -> None:
    claude = _tree(tmp_path)
    _git(tmp_path, "init", "-q")
    (claude / "agents" / "stray.md").write_text(NO_REX)
    _git(tmp_path, "add", ".")
    res = _run(claude)
    assert res.returncode == 1 and "stray.md" in res.stdout + res.stderr


def test_outside_a_work_tree_the_disk_is_read(tmp_path: Path) -> None:
    claude = _tree(tmp_path)
    (claude / "agents" / "stray.md").write_text(NO_REX)
    res = _run(claude)
    assert res.returncode == 1 and "stray.md" in res.stdout + res.stderr
