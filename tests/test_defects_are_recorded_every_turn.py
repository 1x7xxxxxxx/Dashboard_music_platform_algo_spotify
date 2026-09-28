"""R315 — every turn's defect symptoms are recorded, redacted, and read back as defects.

Type: Test
Uses: .claude/scripts/defect_capture.py, tools/dev/defect_log.py, .claude/hooks/session_summary.py
Depends on: nothing live — synthetic transcripts in tmp_path
Persists in: nothing

What must hold, each able to break without a sound:
1. the three high-precision symptoms are recorded (red test node, traceback in a repo file,
   hook / pre-commit refusal) and the noisy ones are NOT (a non-zero Bash exit, a permission
   denial, a traceback from a throwaway `python3 -` script);
2. nothing that could be a secret reaches the log, and a long test name is not mistaken for one;
3. the transcript is read incrementally — a second call reads nothing, a half-written line
   waits for the next call;
4. the log lives under a gitignored path (the repo is public) and the Stop hook reaches it;
5. a green proves only the nodes it ran; a symptom back after a green is PROPOSED for the
   catalogue's `recurrence:` ticket.

Mutation record (2026-09-29): seen red on `_FAILED` matching nothing (check 1), on the secret
prefix pattern removed from `_REDACT` (check 2), on the offset never written (check 3), on the
green scope filter removed and on `_covers` returning True (check 5 — the second one survived
until a green on ANOTHER file was asserted).
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))
sys.path.insert(0, str(ROOT / "tools" / "dev"))

import defect_capture as dc  # noqa: E402
import defect_log as dl  # noqa: E402

HOOK_REFUSAL = (
    "PreToolUse:Bash hook error: [python3 .../.claude/hooks/guard_destructive.py]: 🚫 BLOCKED\n"
    "   Reason  : `make x 2 >& 1` est tube dans un filtre, et une LIVRAISON suit\n")
TRACEBACK = ("Traceback (most recent call last):\n"
             f'  File "{ROOT}/src/dashboard/utils/colorimetry.py", line 12, in f\n'
             "KeyError: 'x'\n")


def _kinds(text: str, command: str = "") -> list[str]:
    return [s["kind"] for s in dc.symptoms(text, command)]


def test_the_three_signals_are_recorded_and_the_noise_is_not() -> None:
    assert _kinds("FAILED tests/test_a.py::test_b - AssertionError") == ["test_red"]
    assert _kinds(TRACEBACK) == ["traceback"]
    assert dc.symptoms(TRACEBACK)[0]["fingerprint"] == (
        "traceback:KeyError@src/dashboard/utils/colorimetry.py")
    refusal = dc.symptoms(HOOK_REFUSAL)
    assert [s["kind"] for s in refusal] == ["hook_refusal"]
    assert refusal[0]["fingerprint"] == "hook:guard_destructive:est tube dans un filtre, et"
    assert _kinds("fix end of files......................Failed") == ["precommit_refusal"]
    assert _kinds("Exit code 1\n") == []  # grep with no match
    assert _kinds("Permission to use Bash with command x has been denied.") == []
    scratch = 'Traceback (most recent call last):\n  File "<stdin>", line 3\nValueError: x\n'
    assert _kinds(scratch) == []


def test_nothing_that_could_be_a_secret_reaches_the_log() -> None:
    out = dc.redact("mail a.b@example.org key Ab3dEf6hIj9kLm2nOp5qRs8tUv ghp_abcdefghijklmnop1234 "
                    "/home/someone/x")
    assert "@example.org" not in out and "Ab3dEf6h" not in out and "ghp_" not in out
    assert "/home/someone" not in out
    name = "tests/test_a_roi_verdict_needs_a_crossing_and_enough_points.py::test_t7_the_page"
    assert dc.redact(name) == name, "a test name is not a secret"


def _line(content: str, tool_id: str = "t1", command: str = "") -> str:
    use = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_id, "input": {"command": command}}]}}
    res = {"type": "user", "timestamp": "2026-09-29T10:00:00Z", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": content}]}}
    return json.dumps(use) + "\n" + json.dumps(res) + "\n"


def test_the_transcript_is_read_once_and_a_half_line_waits(tmp_path) -> None:
    transcript, log = tmp_path / "s.jsonl", tmp_path / "defects.jsonl"
    transcript.write_text(_line("FAILED tests/test_a.py::test_b"))
    assert dc.capture(str(transcript), "s", log) == 1
    assert dc.capture(str(transcript), "s", log) == 0, "the same turn recorded twice"
    whole = _line("FAILED tests/test_c.py::test_d", "t2")
    with transcript.open("a") as f:
        f.write(whole[:-10])
    assert dc.capture(str(transcript), "s", log) == 0, "a half-written line was consumed"
    with transcript.open("a") as f:
        f.write(whole[-10:])
    assert dc.capture(str(transcript), "s", log) == 1


def test_the_log_is_gitignored_and_the_stop_hook_reaches_it() -> None:
    rel = dc.LOG.relative_to(ROOT).as_posix()
    assert subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT).returncode == 0, (
        f"{rel} would be committed to a PUBLIC repo")
    tree = ast.parse((ROOT / ".claude/hooks/session_summary.py").read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    called = {c.func.id for c in ast.walk(main)
              if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "record_defects" in called, "the capture exists but the Stop hook never calls it"


def _ev(kind: str, ts: str, session: str = "s1", fp: str = "test:tests/test_a.py::test_b",
        **kw) -> dict:
    return {"kind": kind, "ts": ts, "session": session, "fingerprint": fp, "excerpt": "x", **kw}


def test_a_green_proves_only_what_it_ran_and_a_return_is_proposed() -> None:
    red1 = _ev("test_red", "2026-09-27T10:00")
    green_changed = _ev("test_green", "2026-09-27T10:05", fp="green", scope="unknown", files=[])
    assert dl.classify([red1, green_changed])[0]["status"] == "open"
    green_other = _ev("test_green", "2026-09-27T10:05", fp="green", scope="files",
                      files=["tests/test_other.py"])
    assert dl.classify([red1, green_other])[0]["status"] == "open", (
        "a green on ANOTHER file proves nothing about this node")
    green_file = _ev("test_green", "2026-09-27T10:05", fp="green", scope="files",
                     files=["tests/test_a.py"])
    assert dl.classify([red1, green_file])[0]["status"] == "transient"
    red2 = _ev("test_red", "2026-09-28T09:00", session="s2")
    row = dl.classify([red1, green_file, red2])[0]
    assert row["recurrence_proposal"] == "recurrence:2026-09-27,2026-09-28"
    assert dl.classify([red1, red2])[0]["recurrence_proposal"] is None, (
        "never green in between: one long defect, not a return")
