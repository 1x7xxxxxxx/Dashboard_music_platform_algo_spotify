"""R464 — a change committed but not pushed is still selected by `select_tests.py`.

Type: Test
Uses: .claude/scripts/select_tests.py (changed_files)
Depends on: git (a throwaway repo with a bare upstream, under tmp_path)

2026-10-08: `make test-changed` ran AFTER a commit. Diffing against `HEAD` it saw nothing,
selected no test, stamped the tree green, and the pre-push gate let the commit go; CI
went red on a ranking test that reads the very file committed. The base is now the
merge-base with the upstream, so every unpushed commit counts.

Mutation record (2026-10-08): `_unpushed_base` returning "HEAD" → red; the merge-base
probe made to report a git failure without upstream → red.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "_r464_select_tests", Path(__file__).resolve().parents[1] / ".claude" / "scripts" / "select_tests.py")
sel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sel)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   cwd=cwd, check=True, capture_output=True)


def _repo(tmp_path: Path, upstream: bool) -> Path:
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "notes.md").write_text("a\n")
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "base")
    if upstream:
        _git(tmp_path, "init", "-q", "--bare", "up.git")
        _git(work, "remote", "add", "origin", str(tmp_path / "up.git"))
        _git(work, "push", "-q", "-u", "origin", "main")
    (work / "notes.md").write_text("b\n")
    _git(work, "commit", "-qam", "unpushed")
    return work


def test_an_unpushed_commit_is_a_change(tmp_path: Path) -> None:
    assert sel.changed_files(_repo(tmp_path, upstream=True), None) == ["notes.md"]


def test_without_an_upstream_the_base_is_head_and_no_failure_is_reported(tmp_path: Path) -> None:
    sel._DERNIERE_PANNE_GIT = None
    assert sel.changed_files(_repo(tmp_path, upstream=False), None) == []
    assert sel._DERNIERE_PANNE_GIT is None
