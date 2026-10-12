"""The Stop gate refuses « done » when code changed after the last test verdict (R549).

Type: Test
Uses: git (a fabricated repo with a bare upstream), os.utime
Depends on: .claude/hooks/require_verdict_after_edit.py, .claude/hooks/_verdict.py
Persists in: tmp_path only

Why: an agent claims a problem solved because it modified code. A mod cannot stop that
(`turn.complete` only observes); a Stop hook can, once. The trap the gate is built
around: `tee` truncates `.pytest-last.log` at START and keeps writing, so a suite that
began BEFORE the last edit has a fresh log — only `.pytest-last.started` dates the tree.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
_GREEN = "12 passed, 1 skipped in 3.40s\n"
_RED = "2 failed, 10 passed in 3.40s\n"


def _load():
    import sys
    sys.path.insert(0, str(_HOOKS))
    spec = importlib.util.spec_from_file_location("stop_gate", _HOOKS / "require_verdict_after_edit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load()


def _sh(cwd: Path, *args: str) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    remote, root = tmp_path / "remote.git", tmp_path / "work"
    _sh(tmp_path, "git", "init", "-q", "--bare", str(remote))
    _sh(tmp_path, "git", "init", "-q", "-b", "main", str(root))
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _sh(root, "git", "config", k, v)
    (root / "app.py").write_text("x = 1\n")
    (root / "notes.md").write_text("a\n")
    _sh(root, "git", "add", ".")
    _sh(root, "git", "commit", "-q", "--no-verify", "-m", "init")
    _sh(root, "git", "remote", "add", "origin", str(remote))
    _sh(root, "git", "push", "-q", "-u", "origin", "main")
    return root


def _at(path: Path, t: float, text: str | None = None) -> None:
    if text is not None:
        path.write_text(text)
    os.utime(path, (t, t))


def _suite(root: Path, started: float, finished: float, summary: str = _GREEN) -> None:
    _at(root / ".pytest-last.started", started, "")
    _at(root / ".pytest-last.log", finished, "....\n" + summary)


def _decide(root: Path, log: Path | None = None, **payload) -> dict | None:
    return gate.decide(root, payload, log)


def test_an_edit_after_the_verdict_blocks(repo: Path) -> None:
    _suite(repo, 1000, 1100)
    _at(repo / "app.py", 2000, "x = 2\n")
    out = _decide(repo)
    assert out and out["decision"] == "block" and "app.py" in out["reason"]


def test_a_verdict_after_the_edit_lets_the_turn_end(repo: Path) -> None:
    _at(repo / "app.py", 1000, "x = 2\n")
    _suite(repo, 2000, 2100)
    assert _decide(repo) is None


def test_a_red_verdict_after_the_edit_is_a_verdict_too(repo: Path) -> None:
    """Reporting a red suite is an honest end of turn; the gate asks for a verdict, not green."""
    _at(repo / "app.py", 1000, "x = 2\n")
    _suite(repo, 2000, 2100, _RED)
    assert _decide(repo) is None
    assert gate.verdict(repo).state == "rouge" and gate.verdict(repo).failed == 2


def test_the_continued_turn_may_stop(repo: Path) -> None:
    _at(repo / "app.py", 2000, "x = 2\n")
    assert _decide(repo, stop_hook_active=True) is None


def test_a_documentation_edit_never_blocks(repo: Path) -> None:
    _suite(repo, 1000, 1100)
    _at(repo / "notes.md", 2000, "b\n")
    assert _decide(repo) is None


def test_a_suite_started_before_the_edit_is_stale_even_with_a_fresh_log(repo: Path) -> None:
    """THE trap: the log was written after the edit, but the run began before it."""
    _at(repo / "app.py", 1500, "x = 2\n")
    _suite(repo, started=1000, finished=2000)
    assert gate.verdict(repo).state == "périmé"
    assert _decide(repo) is not None


def test_no_verdict_at_all_and_code_changed_blocks(repo: Path) -> None:
    _at(repo / "app.py", 2000, "x = 2\n")
    assert gate.verdict(repo).state == "absent"
    assert _decide(repo) is not None


def test_an_unpushed_commit_still_needs_its_verdict(repo: Path) -> None:
    _suite(repo, 1000, 1100)
    _at(repo / "app.py", 2000, "x = 2\n")
    _sh(repo, "git", "commit", "-q", "--no-verify", "-am", "change")
    assert _decide(repo) is not None


def test_pushed_code_has_nothing_pending(repo: Path) -> None:
    _at(repo / "app.py", 2000, "x = 2\n")
    _sh(repo, "git", "commit", "-q", "--no-verify", "-am", "change")
    _sh(repo, "git", "push", "-q")
    assert _decide(repo) is None


def test_the_same_edit_is_blocked_once(repo: Path, tmp_path: Path) -> None:
    log = tmp_path / "stop-gate.jsonl"
    _at(repo / "app.py", 2000, "x = 2\n")
    assert _decide(repo, log) is not None
    assert _decide(repo, log) is None, "the gate blocked twice on the same edit"
    _at(repo / "app.py", 3000, "x = 3\n")
    assert _decide(repo, log) is not None, "a NEW edit must be blocked again"
    assert len(log.read_text().splitlines()) == 2


def test_the_hook_prints_the_block_as_json(repo: Path) -> None:
    import json
    import sys
    _at(repo / "app.py", 2000, "x = 2\n")
    r = subprocess.run([sys.executable, str(_HOOKS / "require_verdict_after_edit.py")],
                       input=json.dumps({"cwd": str(repo)}), capture_output=True,
                       text=True, timeout=30, env={**os.environ, "HOOK_TRACE_DIR": str(repo.parent)})
    assert r.returncode == 0
    assert json.loads(r.stdout)["decision"] == "block"
