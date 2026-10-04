"""R360 / REQ-HARN-10 — the Stop hook suggest_sweep.py points at /sweep after a fix.

Type: Test
Uses: .claude/hooks/suggest_sweep.py (run as a subprocess, as the Stop chain runs it)
Depends on: git (a throwaway repository in tmp_path)
Persists in: nothing (the hook only reads; the repository lives in tmp_path)

Contract promised by the hook's docstring:
1. a session with a fix-shaped commit since the session marker prints ONE /sweep line
   on stderr, naming the signal, and exits 0 (never blocks);
2. a session with none of the four signals stays silent;
3. without the error-class catalogue, /sweep is not wired: silent even after a fix.

The hook resolves its repo root from the cwd (first parent holding `.claude/`), so
running it with cwd=tmp_path keeps every read inside the throwaway repository.

Mutation record (2026-10-04): seen red with `if commits:` changed to `if False:` in
`_detect` (test 1: "assert 'signal: fix-commit' in ''"), and with the catalogue
early-exit `if not (repo_root / _CATALOGUE).exists()` inverted (tests 1 and 3 red);
R360: with the French words removed from `_FIX_RE` (the French-commit test red).
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "suggest_sweep.py"
CATALOGUE = ".claude/dev-docs/error-classes.md"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo, check=True, capture_output=True,
    )


def _repo(tmp_path: Path, *, catalogue: bool = True) -> Path:
    repo = tmp_path.resolve()
    (repo / ".claude" / "sessions").mkdir(parents=True)
    # Session started one minute ago: every commit below is "this session".
    (repo / ".claude" / "sessions" / ".session-start-ts").write_text(str(time.time() - 60))
    (repo / ".gitignore").write_text(".claude/sessions/\n")
    if catalogue:
        (repo / CATALOGUE).parent.mkdir(parents=True)
        (repo / CATALOGUE).write_text("# catalogue\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial import")
    return repo


def _commit(repo: Path, message: str) -> None:
    (repo / "notes.txt").write_text(message + "\n")
    _git(repo, "add", "notes.txt")
    _git(repo, "commit", "-q", "-m", message)


def _run(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)], cwd=repo, input="{}",
        capture_output=True, text=True, timeout=30,
    )


def test_a_fix_commit_in_the_session_prints_one_sweep_suggestion(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "fix the crash on empty upload")
    out = _run(repo)
    assert out.returncode == 0
    assert "signal: fix-commit" in out.stderr
    assert '/sweep "fix the crash on empty upload"' in out.stderr
    assert out.stderr.count("Bugfix-shaped session") == 1
    # The catalogue was not touched: the hint must point at the impact-analysis playbook.
    assert "impact-analysis/SKILL.md" in out.stderr


def test_a_french_fix_commit_is_a_fix_commit(tmp_path: Path) -> None:
    """R360: this repo commits in French; the English-only regex missed 22 of 24 fixes."""
    repo = _repo(tmp_path)
    _commit(repo, "R999 : corrige le plantage sur un import vide")
    out = _run(repo)
    assert out.returncode == 0
    assert "signal: fix-commit" in out.stderr


def test_a_session_without_any_signal_stays_silent(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit(repo, "add the monthly export")
    out = _run(repo)
    assert out.returncode == 0
    assert out.stderr == ""


def test_without_the_catalogue_the_hook_stays_silent_even_after_a_fix(tmp_path: Path) -> None:
    repo = _repo(tmp_path, catalogue=False)
    _commit(repo, "fix the crash on empty upload")
    out = _run(repo)
    assert out.returncode == 0
    assert out.stderr == ""
