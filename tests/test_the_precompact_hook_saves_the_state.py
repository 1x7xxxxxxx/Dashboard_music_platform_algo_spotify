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

R414 (REQ-HARN-06): the snapshot also carries `night_run.py status` — where a long session
stood, the one thing a resume after compaction lacked. The block carries a clock, so it
is outside the state comparison; it is bounded; a failure is one note line; and it is the
`status` subcommand only (`check` calls `gh`). Mutations (2026-10-05): block kept in
`_strip_timestamps` → RED (a second snapshot for one state); the line cap removed → RED;
`status` → `check` → RED.
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


def _run(repo: Path) -> str:
    r = subprocess.run([sys.executable, str(HOOK)], cwd=repo, input="{}",
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


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
    said = _run(repo)
    # Red three times under a full suite (2026-10-05, 2026-10-06), never reproduced alone
    # nor under 12 parallel runs: the message carries what the hook saw, so the next
    # occurrence names its own cause.
    assert len(_snapshots(repo)) == 2, (
        said, [(f.name, f.read_text(encoding="utf-8")) for f in _snapshots(repo)])


_FAKE = """import sys, time
open(".claude/sessions/argv.txt", "w").write(" ".join(sys.argv[1:]))  # gitignored, like the snapshots
print("OÙ J'EN SUIS — " + repr(time.time()))
for i in range(80):
    print(f"line {i}")
"""


def _fake_night_run(repo: Path, body: str = _FAKE) -> Path:
    target = repo / "tools" / "dev" / "night_run.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)
    return target


def test_the_snapshot_carries_a_bounded_night_status_outside_the_state(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _fake_night_run(repo)
    (repo / "a.py").write_text("x = 2\n")
    _run(repo)
    text = (repo / ".claude" / "sessions" / "latest.md").read_text(encoding="utf-8")
    assert "## Night status" in text and "OÙ J'EN SUIS" in text
    assert "line 39" not in text and "(… truncated)" in text, "the block is not bounded"
    assert (repo / ".claude" / "sessions" / "argv.txt").read_text() == "status", "only `status` — `check` calls gh"

    time.sleep(1.1)
    _run(repo)  # the fake prints a new clock: same state, different block
    assert len(_snapshots(repo)) == 1, "a night-status clock made a second snapshot"


def _hook_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pre_compact_r414", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_failing_or_slow_night_status_is_one_note_line(tmp_path: Path) -> None:
    hook = _hook_module()
    assert hook._night_status(tmp_path) == "(night_run.py absent)"
    _fake_night_run(tmp_path, "import sys; sys.exit(3)")
    assert hook._night_status(tmp_path) == "(night-status unavailable: exit 3)"
    _fake_night_run(tmp_path, "import time; time.sleep(5)")
    assert hook._night_status(tmp_path, timeout=0.5) == "(night-status unavailable: TimeoutExpired)"


def test_a_clock_step_back_never_overwrites_a_snapshot(tmp_path: Path) -> None:
    """R420 — the WSL wall clock steps BACK (Hyper-V TimeSync, −1.78 s measured 2026-10-06):
    two calls can compute the same `session-<second>.md`. Every name the hook could pick in
    the window is taken by a different state; none may be rewritten, and the new state lands."""
    from datetime import datetime, timedelta

    repo = _repo(tmp_path)
    sessions = repo / ".claude" / "sessions"
    sessions.mkdir()
    now = datetime.now()
    taken = {}
    for s in range(-2, 6):  # 8 files: retention keeps 10, the new one must not evict any
        f = sessions / f"session-{(now + timedelta(seconds=s)):%Y%m%d-%H%M%S}.md"
        f.write_text(f"older state {s}\n", encoding="utf-8")
        taken[f] = f.read_text(encoding="utf-8")
    (repo / "a.py").write_text("x = 2\n")
    _run(repo)
    assert {f: f.read_text(encoding="utf-8") for f in taken} == taken, "a snapshot was overwritten"
    new = [f for f in _snapshots(repo) if f not in taken]
    assert len(new) == 1 and "a.py" in new[0].read_text(encoding="utf-8")
