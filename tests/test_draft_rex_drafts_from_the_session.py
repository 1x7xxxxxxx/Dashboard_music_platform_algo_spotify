"""R360 / REQ-HARN-11 — the Stop hook draft_rex.py drafts one REX per tool edited this session.

Type: Test
Uses: .claude/hooks/draft_rex.py (run as a subprocess, as the Stop chain runs it)
Depends on: nothing beyond the interpreter (the hook reads no git)
Persists in: nothing (pending-rex.md is written under tmp_path only)

Contract promised by the hook's docstring:
1. observations since the session marker, on files under
   .claude/{agents,skills,commands,rules,hooks,scripts} (.md/.py), become one proposal
   per file in .claude/sessions/pending-rex.md — edits outside those dirs and edits
   before the session start are not proposed;
2. when no tool was modified, it writes nothing and prints nothing;
3. it never blocks: exit 0.

The hook resolves its repo root from the cwd (first parent holding `.claude/`) and
reads `.claude/homunculus/<root name>/observations.jsonl`, so running it with
cwd=tmp_path keeps every read and write inside the throwaway directory.

Mutation record (2026-10-04): seen red with `if not _is_tool_path(rel_str): continue`
removed (test 1: "assert '## src/views/home.py' not in ...", and test 2: "assert not
True", pending-rex.md written), and with the `entry_ts < start_ts` filter removed
(test 1: "assert '## .claude/agents/old.md' not in ...", the pre-session edit proposed);
R360: with the `_holds_human_input` guard short-circuited (`if False and …`, test 3 red).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "draft_rex.py"


def _ts(epoch: float) -> str:
    # observe.py writes local time with this exact format; draft_rex parses it back.
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(epoch))


def _root(tmp_path: Path, edits: list[tuple[str, float]]) -> Path:
    root = tmp_path.resolve()
    (root / ".claude" / "sessions").mkdir(parents=True)
    now = time.time()
    (root / ".claude" / "sessions" / ".session-start-ts").write_text(str(now - 3600))
    obs = root / ".claude" / "homunculus" / root.name / "observations.jsonl"
    obs.parent.mkdir(parents=True)
    lines = [
        json.dumps({"ts": _ts(now - age), "tool": "Edit", "file": str(root / rel)})
        for rel, age in edits
    ]
    obs.write_text("\n".join(lines) + "\n")
    return root


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)], cwd=root, input="{}",
        capture_output=True, text=True, timeout=30,
    )


def test_tool_edits_of_this_session_are_drafted_one_per_file(tmp_path: Path) -> None:
    root = _root(tmp_path, [
        (".claude/hooks/guard.py", 60),
        (".claude/hooks/guard.py", 30),
        (".claude/skills/sweep/SKILL.md", 45),
        ("src/views/home.py", 20),            # product code, not a tool
        (".claude/agents/old.md", 2 * 3600),  # before the session marker
    ])
    out = _run(root)
    assert out.returncode == 0
    pending = root / ".claude" / "sessions" / "pending-rex.md"
    text = pending.read_text(encoding="utf-8")
    assert "## .claude/hooks/guard.py" in text
    assert "## .claude/skills/sweep/SKILL.md" in text
    assert "# observed: 2 edit(s)" in text
    assert "## src/views/home.py" not in text
    assert "## .claude/agents/old.md" not in text
    assert text.count("validated: false") == 2
    assert "2 REX draft(s) pending" in out.stderr


def test_a_session_that_touched_no_tool_writes_nothing(tmp_path: Path) -> None:
    root = _root(tmp_path, [("src/views/home.py", 20), ("README.md", 10)])
    out = _run(root)
    assert out.returncode == 0
    assert not (root / ".claude" / "sessions" / "pending-rex.md").exists()
    assert out.stderr == ""


def test_a_draft_a_human_filled_survives_the_next_stop(tmp_path: Path) -> None:
    """R360: every Stop used to overwrite pending-rex.md, erasing the human's filling."""
    root = _root(tmp_path, [(".claude/hooks/guard.py", 60)])
    pending = root / ".claude" / "sessions" / "pending-rex.md"
    assert _run(root).returncode == 0
    untouched = pending.read_text(encoding="utf-8")
    filled = untouched.replace('issue: "?"', 'issue: "the guard read prose"', 1)
    assert filled != untouched
    pending.write_text(filled, encoding="utf-8")
    out = _run(root)
    assert out.returncode == 0
    assert pending.read_text(encoding="utf-8") == filled
    # An untouched draft is still refreshed: only human input freezes the file.
    pending.write_text(untouched + "stale\n", encoding="utf-8")
    assert _run(root).returncode == 0
    assert "stale" not in pending.read_text(encoding="utf-8")
