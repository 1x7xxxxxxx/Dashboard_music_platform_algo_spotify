"""R357 — skills, rules, workflows and playbook injections are counted, not assumed.

Type: Test
Uses: .claude/scripts/usage_report.py, .claude/hooks/inject_context.py
Depends on: nothing live — synthetic transcript lines and a tmp log
Persists in: nothing

Before R357 only agents were counted: `curator/usage.json` had been stale since
2026-06-19, rules were never measured, and `inject_context.py` wrote nothing, so a
playbook injected 98 times was indistinguishable from one injected never.
What must hold:
1. a `Skill` call counts under its skill, a `Workflow` call under its name, with a date;
2. a rule loaded twice in one session counts ONE session;
3. an injection appended by the hook is read back by the report;
4. the hook's logger never raises (a hook that raises blocks the prompt).

Mutation record (2026-10-04): seen red with the Skill branch removed, the rule count
per line instead of per session, and the injection log path desynchronised.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))

import inject_context  # noqa: E402
import usage_report as ur  # noqa: E402


def _tool(name: str, inp: dict, ts: str = "2026-10-04T10:00:00.000Z") -> str:
    return json.dumps({"timestamp": ts, "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}})


def test_skills_and_workflows_are_counted_with_their_last_date(tmp_path, monkeypatch) -> None:
    rule = "Contents of /x/.claude/rules/python.md (project instructions)"
    (tmp_path / "s1.jsonl").write_text("\n".join([
        _tool("Skill", {"skill": "capitalise"}),
        _tool("Skill", {"skill": "capitalise"}, "2026-10-05T10:00:00.000Z"),
        _tool("Workflow", {"name": "engineering-loop"}),
        json.dumps({"message": {"content": rule}}),
        json.dumps({"message": {"content": rule}}),
    ]))
    (tmp_path / "s2.jsonl").write_text(json.dumps({"message": {"content": rule}}))
    monkeypatch.setattr(ur, "_TRANSCRIPTS", tmp_path)
    monkeypatch.setattr(ur, "_INJECTIONS", tmp_path / "none.jsonl")
    data = ur.read()
    assert data["skills"] == {"capitalise": 2}
    assert data["workflows"] == {"engineering-loop": 1}
    assert data["rules"] == {"python": 2}
    assert data["last_seen"]["skill:capitalise"].startswith("2026-10-05")


def test_an_injection_logged_by_the_hook_is_read_by_the_report(tmp_path, monkeypatch) -> None:
    assert Path(inject_context._LOG).resolve() == ur._INJECTIONS.resolve()
    log = tmp_path / "sessions" / "injections.jsonl"
    inject_context.log_injection(["workflows/bug-resolution.md"], "s1", str(log))
    inject_context.log_injection(["workflows/bug-resolution.md",
                                  "workflows/architecture-change.md"], "s2", str(log))
    monkeypatch.setattr(ur, "_INJECTIONS", log)
    got = ur.injections()
    assert got["counts"] == {"workflows/bug-resolution.md": 2,
                             "workflows/architecture-change.md": 1}


def test_the_hook_logger_never_raises(tmp_path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("")
    inject_context.log_injection(["x"], "s", str(blocker / "sub" / "log.jsonl"))
