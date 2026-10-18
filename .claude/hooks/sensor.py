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
    The bug→sweep→guard workflow is a PLAYBOOK the model follows (`skills/impact-analysis/SKILL.md`,
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

  3. **SubagentStop → the agent's journal** (T93 of the baseline, 2026-10-18, owner: « après
     chaque utilisation on saisit un journal pour tracer les actions, les problèmes rencontrés, le
     rex de configuration du harnais »). The payload carries `agent_transcript_path`; the row now
     says what the agent DID (`actions`: each tool and its target, `tools`: counts), what went
     WRONG (`problems`: each tool_result flagged `is_error`, with a `harness` category — permission,
     hook, budget, timeout, not-found, read-before-edit, other), what it RETURNED (`outcome`: the
     handback, truncated) and how long it took. The REX itself is not written here (records,
     never reasons): the baseline's `tools/dev/agent_rex.py` reads these rows across the fleet and
     turns a problem that recurs into a harness-configuration REX.

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
import re
import sys
import time
from pathlib import Path
import sys as _sys  # R365 — one trace line per run, even for a silent hook
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "hooks"))
from _hook_trace import trace as _trace  # noqa: E402
_trace(__file__)

_MAX_ENTRIES = 2000        # hard cap; oldest dropped. An unbounded log is a log nobody opens.
_CMD_CHARS = 160
_MAX_ACTIONS = 40          # a journal row stays one line a human reads
_TARGET_CHARS = 80
_OUTCOME_CHARS = 400
_TRANSCRIPT_MAX_BYTES = 20_000_000

# The harness category of a failed tool call: what in the Claude Code configuration it points at.
_HARNESS = (
    ("permission", re.compile(r"permission|not allowed|denied|requires approval|auto mode", re.I)),
    ("hook", re.compile(r"hook|blocked by|PreToolUse", re.I)),
    ("budget", re.compile(r"budget|quota|rate limit|usage limit", re.I)),
    ("timeout", re.compile(r"timed? ?out|timeout", re.I)),
    ("read-before-edit", re.compile(r"has not been read|read it first|must read", re.I)),
    ("not-found", re.compile(r"no such file|not found|does not exist|command not found", re.I)),
)


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


def _target(inp: dict) -> str:
    v = (inp.get("command") or inp.get("file_path") or inp.get("pattern") or inp.get("path")
         or inp.get("url") or inp.get("query") or inp.get("description") or "")
    return " ".join(str(v).split())[:_TARGET_CHARS]


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return json.dumps(content, ensure_ascii=False) if content is not None else ""


def harness_category(error: str) -> str:
    for name, rx in _HARNESS:
        if rx.search(error):
            return name
    return "other"


def journal(transcript: str) -> dict:
    """What the agent did, from its own transcript: actions, problems, outcome, duration.
    Empty when the transcript cannot be read — the row still says which agent ran."""
    try:
        path = Path(transcript)
        if not transcript or path.stat().st_size > _TRANSCRIPT_MAX_BYTES:
            return {}
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
    except (OSError, ValueError):
        return {}
    uses: dict = {}
    actions: list = []
    tools: dict = {}
    problems: list = []
    outcome = handback = ""
    stamps = [r.get("timestamp") for r in rows if isinstance(r, dict) and r.get("timestamp")]
    for r in rows:
        msg = r.get("message") if isinstance(r, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                name, inp = b.get("name", "?"), b.get("input") or {}
                if name == "SubagentHandback":
                    handback = _text(inp.get("message"))
                    continue
                uses[b.get("id")] = (name, _target(inp))
                tools[name] = tools.get(name, 0) + 1
                if len(actions) < _MAX_ACTIONS:
                    actions.append(f"{name}: {_target(inp)}" if _target(inp) else name)
            elif b.get("type") == "tool_result" and b.get("is_error"):
                name, target = uses.get(b.get("tool_use_id"), ("?", ""))
                err = " ".join(_text(b.get("content")).split())[:_CMD_CHARS]
                problems.append({"tool": name, "target": target, "error": err,
                                 "harness": harness_category(err)})
            elif b.get("type") == "text" and r.get("type") == "assistant":
                outcome = b.get("text", "") or outcome   # the last text, when no handback
    out = {"tools": tools, "actions": actions, "problems": problems,
           "outcome": " ".join((handback or outcome).split())[:_OUTCOME_CHARS]}
    try:
        from datetime import datetime
        t0, t1 = (datetime.fromisoformat(s.replace("Z", "+00:00")) for s in (stamps[0], stamps[-1]))
        out["duration_s"] = round((t1 - t0).total_seconds())
    except (IndexError, ValueError, TypeError):
        pass
    return out


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
        entry.update(journal(data.get("agent_transcript_path") or ""))
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
