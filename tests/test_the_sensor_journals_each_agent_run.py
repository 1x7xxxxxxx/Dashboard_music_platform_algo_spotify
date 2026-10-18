"""An agent run leaves a journal row: its actions, its problems, its outcome (baseline T93).

guard_scope: `sensor.py` on SubagentStop with an `agent_transcript_path` — the tools and targets,
the tool_results flagged `is_error` with their harness category, the handback, the duration;
and a missing transcript still records the agent. NOT covered: turning the problems into a REX
— that is the baseline's `tools/dev/agent_rex.py`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SENSOR = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "sensor.py"


def _transcript(tmp: Path) -> Path:
    rows = [
        {"type": "user", "timestamp": "2026-10-18T10:00:00.000Z", "message": {"content": "relis"}},
        {"type": "assistant", "timestamp": "2026-10-18T10:00:05.000Z", "message": {"content": [
            {"type": "tool_use", "id": "a", "name": "Bash", "input": {"command": "git diff -U5"}},
            {"type": "tool_use", "id": "b", "name": "Edit", "input": {"file_path": "/r/x.py"}}]}},
        {"type": "user", "timestamp": "2026-10-18T10:00:06.000Z", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "a", "content": "diff…", "is_error": False},
            {"type": "tool_result", "tool_use_id": "b", "is_error": True,
             "content": "File has not been read yet. Read it first before writing to it."}]}},
        {"type": "assistant", "timestamp": "2026-10-18T10:01:00.000Z", "message": {"content": [
            {"type": "tool_use", "id": "c", "name": "SubagentHandback",
             "input": {"message": "VERDICT: BLOCK — 1 HIGH"}}]}},
    ]
    p = tmp / "agent.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def _run(tmp: Path, payload: dict) -> dict:
    (tmp / ".claude").mkdir(exist_ok=True)
    body = json.dumps({"hook_event_name": "SubagentStop", "agent_type": "code-critic",
                       "agent_id": "abc", **payload})
    r = subprocess.run([sys.executable, str(SENSOR)], input=body, text=True, cwd=tmp,
                       capture_output=True, timeout=30)
    assert r.returncode == 0
    lines = (tmp / ".claude" / "homunculus" / tmp.name / "sensor.jsonl").read_text().splitlines()
    return json.loads(lines[-1])


def test_an_agent_run_journals_its_actions_problems_and_outcome(tmp_path) -> None:
    row = _run(tmp_path, {"agent_transcript_path": str(_transcript(tmp_path))})
    assert row["agent"] == "code-critic"
    assert row["tools"] == {"Bash": 1, "Edit": 1}
    assert row["actions"] == ["Bash: git diff -U5", "Edit: /r/x.py"]
    assert row["problems"] == [{"tool": "Edit", "target": "/r/x.py", "harness": "read-before-edit",
                                "error": "File has not been read yet. Read it first before writing to it."}]
    assert row["outcome"] == "VERDICT: BLOCK — 1 HIGH"
    assert row["duration_s"] == 60


def test_an_unreadable_transcript_still_records_the_agent(tmp_path) -> None:
    row = _run(tmp_path, {"agent_transcript_path": str(tmp_path / "absent.jsonl")})
    assert row["agent"] == "code-critic" and "actions" not in row
