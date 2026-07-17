#!/usr/bin/env python3
"""SubagentStop + PostToolUseFailure — the two signals nothing was recording.

IT RECORDS. IT DOES NOT REASON, AND IT CANNOT ORCHESTRATE. Both halves matter:

  · **Records, never reasons.** Across this config's 7 sibling repos, the one component that ever
    worked is the one that records: msdr's `usage_telemetry.py` (63 lines) produced 2 months of
    honest data, while its `curator.py` (250 lines of analysis ON that data) was never run, and when
    finally executed recommended archiving the config's most-used skill. Build sensors; earn analysts
    with data.
  · **Cannot orchestrate — this is a HARNESS FACT, not a design choice.** A hook cannot spawn an
    agent ("deterministic agent launching is NOT supported"), and `PostToolUseFailure` can neither
    block nor react — it is informational. So "OnError → launch a root-cause agent" is NOT
    implementable, here or anywhere. Written down because the architecture it belongs to was
    designed around the assumption that it was, and someone will assume it again.
    The bug→sweep→guard workflow is a PLAYBOOK the model follows (`skills/impact-analysis.md`,
    mandatory via CLAUDE.md), triggered by a rule + keyword injection. That is the only shape that
    exists.

WHAT IT CAPTURES, and why each was a hole:

  1. **SubagentStop → which agent ran.** `agent_type` is in the payload. Until 2026-07-17 nothing
     recorded it: `observe.py` matches `Write|Edit` only, and msdr's `usage.json` has no agent
     category at all. So "are my agents used?" was unanswerable in every sibling repo — while a
     proposal for 25 more was on the table. The transcripts answered it retrospectively (4 of 6
     declared agents: ZERO invocations, ever; 84% of traffic to built-ins). This makes it live, and
     — unlike the transcript, which is machine-local and outside the repo — it writes INTO the repo,
     so it travels and it feeds the `_AGENT_FLOOR` ratchet.
  2. **PostToolUseFailure → what actually broke.** CLAUDE.md says "toute erreur produit un REX" and
     there was no input to that rule: nothing recorded a failure. `draft_rex.py` drafts from
     observations + diff, i.e. from what SUCCEEDED. Now a failed command leaves a row, and the REX
     draft has raw material.

Always exits 0. A sensor that can break a session is a sensor people delete.

---
rex:
  - date: 2026-07-17
    issue: "An architecture was designed around 'error detected -> hook launches Impact Analyzer -> RCA -> ...'. A hook cannot spawn an agent, and PostToolUseFailure can neither block nor react — it is informational only. The whole orchestration premise was unimplementable, and nothing in the repo said so."
    fix: "sensor.py records SubagentStop (agent_type) and PostToolUseFailure, and its docstring states it observes and cannot orchestrate. Same rule added to CLAUDE.md. The bug->sweep->guard loop stays a playbook the model follows (impact-analysis.md), triggered by a rule + keyword injection — the only shape that exists."
    severity: warn
    ref: "CLAUDE.md — 'A hook OBSERVES; it does not ORCHESTRATE'"
---
"""
import json
import os
import sys
import time
from pathlib import Path

_MAX_ENTRIES = 2000        # hard cap; oldest dropped. An unbounded log is a log nobody opens.
_CMD_CHARS = 160


def find_repo_root() -> Path:
    path = Path(os.getcwd())
    while path != path.parent:
        if (path / ".claude").exists():
            return path
        path = path.parent
    return Path(os.getcwd())


def _append(repo_root: Path, entry: dict) -> None:
    d = repo_root / ".claude" / "homunculus" / (repo_root.name or "default")
    try:
        d.mkdir(parents=True, exist_ok=True)
        f = d / "sensor.jsonl"
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        lines = f.read_text(encoding="utf-8").splitlines()
        if len(lines) > _MAX_ENTRIES:
            f.write_text("\n".join(lines[-_MAX_ENTRIES:]) + "\n", encoding="utf-8")
    except OSError:
        pass                # never block on a sensor failure


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    event = data.get("hook_event_name", "")
    entry: dict = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event}

    if event == "SubagentStop":
        # THE row that did not exist. `agent_type` is what the question needs — not the prompt,
        # which can be thousands of tokens and would blow the cap.
        entry["agent"] = data.get("agent_type") or "(unknown)"
        entry["agent_id"] = (data.get("agent_id") or "")[:12]
    elif event in ("PostToolUseFailure", "PostToolUse"):
        # PostToolUse is accepted so this hook still records if the event is ever re-pointed; it
        # only writes on an ACTUAL failure, so a success does not create noise.
        resp = data.get("tool_response") or data.get("tool_result") or {}
        failed = event == "PostToolUseFailure" or (
            isinstance(resp, dict) and (resp.get("is_error") or resp.get("interrupted")))
        if not failed:
            sys.exit(0)
        tool_input = data.get("tool_input") or {}
        entry["tool"] = data.get("tool_name", "")
        entry["target"] = (tool_input.get("command") or tool_input.get("file_path") or "")[:_CMD_CHARS]
        err = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
        entry["error"] = err[:_CMD_CHARS]
    else:
        sys.exit(0)

    _append(find_repo_root(), entry)
    sys.exit(0)


if __name__ == "__main__":
    main()
