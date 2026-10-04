"""R357 — the PreCompact hook writes the state a compacted session resumes from.

Type: Test
Uses: .claude/hooks/pre_compact.py, .claude/settings.json
Depends on: git (a throwaway repository in tmp_path)
Persists in: nothing

Auto-compaction is the one event of a long session that no other probe saw: the hook
had no test, so a crash there would cost the resume context silently. What must hold:
1. it is registered under PreCompact in settings.json;
2. on a dirty tree it writes `session-*.md` and `latest.md`, naming the modified file;
3. an unchanged state writes no second snapshot (retention would evict a real one);
4. a changed state does.

Mutation record (2026-10-04): seen red with the hook unregistered, with the
`_same_state` short-circuit removed (a second identical snapshot), and with the
git status lines dropped from the content.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "pre_compact.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / ".gitignore").write_text(".claude/sessions/\n")  # as in this repo
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "add", "a.py", ".gitignore")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return tmp_path


def _run(repo: Path) -> None:
    r = subprocess.run([sys.executable, str(HOOK)], cwd=repo, input="{}",
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr


def _snapshots(repo: Path) -> list[Path]:
    return sorted((repo / ".claude" / "sessions").glob("session-*.md"))


def test_the_hook_is_registered_for_precompact() -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [h["command"] for entry in settings["hooks"].get("PreCompact", [])
                for h in entry.get("hooks", [])]
    assert any("pre_compact.py" in c for c in commands), commands


def test_a_dirty_tree_is_saved_once_per_state(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "a.py").write_text("x = 2\n")
    _run(repo)
    first = _snapshots(repo)
    assert len(first) == 1
    assert "a.py" in first[0].read_text(encoding="utf-8")
    assert (repo / ".claude" / "sessions" / "latest.md").exists()

    time.sleep(1.1)  # same second = same file name: the short-circuit would be untested
    _run(repo)
    assert _snapshots(repo) == first, "an unchanged state wrote a second snapshot"

    (repo / "b.py").write_text("y = 1\n")
    time.sleep(1.1)  # the snapshot name has 1 s resolution
    _run(repo)
    assert len(_snapshots(repo)) == 2
