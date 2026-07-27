#!/usr/bin/env python3
"""Read the sensor that has been running all along — Claude Code's own transcripts.

WHY THIS IS A READER AND NOT A SENSOR, which is the whole lesson.

The plan for today was to BUILD a sensor: patch `observe.py` to record agent invocations, port
msdr's `usage_telemetry.py`, accrue 30 days, then decide. Two measurements killed that plan:

  1. **The sensor already exists and has ~2 months of history.** Every hook payload carries
     `transcript_path`; the transcript JSONL records every `Agent` tool_use WITH its
     `subagent_type`, and every assistant turn's `message.usage`. `session_summary.py:126` has
     been opening that file to count turns — the data was one field away, unread. Patching
     `observe.py` would have started the count at ZERO and thrown away 91 calls of history.
  2. **The patch was wrong anyway.** The tool is named `Agent`. The patch used `"Task"`. It would
     have recorded nothing — a mechanism nobody wired, added by the very work whose subject is
     mechanisms nobody wired. Caught only by measuring the output instead of trusting the plan.

So: no new sensor. A reader. ~60 lines against data that is already there.

WHAT IT SAYS TODAY (measured 2026-07-17, all 20 transcripts):

    Explore 53 · general-purpose 17 · web-research-specialist 8 · Plan 7
    strategic-plan-architect 6 · code-critic 0 · code-architecture-reviewer 0
    build-error-resolver 0 · security-reviewer 0

**4 of the 6 agents CLAUDE.md declares have NEVER been invoked, and 85% of real agent traffic
(77/91) goes to built-ins CLAUDE.md does not mention.** That is the measured answer to "should I
add 25 more agents", and it is why `tests/test_claude_config.py` now fails on a declared-but-unused
agent. A 15-line test that prunes the roster IS the Meta-Agent — it never touches product code, and
unlike msdr's `curator.py` (250 lines, never run, and wrong on first execution) it cannot rot,
because pytest runs it.

USAGE
    python/.venv/bin/python .claude/scripts/usage_report.py            # human summary
    python/.venv/bin/python .claude/scripts/usage_report.py --json     # machine-readable

---
rex:
  - date: 2026-07-17
    issue: "v1 printed 'no transcripts' and exited 0 — a silent failure, in the reader written to detect silent failures. Cause: Claude Code flattens BOTH '/' and '_' to '-' in the transcript dir name, and I only replaced '/'. A reader that finds nothing and calls it fine is decorative."
    fix: "Fixed the derivation and made absence EXIT 1 with the reason. Pinned by test_the_sensor_resolves. The data it unlocked: 4 of 6 declared agents never invoked, 84% of traffic to built-ins CLAUDE.md did not mention — which is the measured answer to 'should we add 25 more agents'."
    severity: warn
    ref: "tests/test_claude_config.py::test_the_sensor_resolves"
---
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib

# Claude Code stores transcripts per project, outside the repo, in a directory whose name is the
# repo path with BOTH separators AND underscores flattened to dashes (`trading_bot` → `trading-bot`).
# That is the harness's convention, not ours — so derive it, then VERIFY it resolves. The first cut
# of this file replaced only "/" and printed "no transcripts" while exiting 0: a reader that finds
# nothing and calls it fine is the silent failure this whole session is about.
_REPO = pathlib.Path(__file__).resolve().parents[2]
_TRANSCRIPTS = (pathlib.Path.home() / ".claude" / "projects"
                / ("-" + str(_REPO).strip("/").replace("/", "-").replace("_", "-")))

# The workflow-trigger sensor, written by inject_context.py. code-critic is an AGENT (SubagentStop
# counts it, above); a workflow is an INJECTION, which nothing recorded until this log — so
# "does engineering-loop ever actually fire?" is now measurable the same way "is code-critic used?" is.
_INJECT_LOG = _REPO / ".claude" / "homunculus" / (_REPO.name or "default") / "inject.jsonl"

# The in-repo agent sensor, written by hooks/sensor.py on SubagentStop. It answers a question the
# transcripts CANNOT: a subagent spawned by a Workflow script is not an `Agent` tool_use, so it is
# invisible to read() above — 216 `workflow-subagent` rows exist here and nowhere else.
#
# ⚠️ THIS FILE WAS WRITTEN FOR 9 DAYS AND READ BY NOBODY (measured 2026-07-27: 735 rows). The only
# other consumer, session_summary.py::_session_failures, filters to PostToolUseFailure and drops
# every SubagentStop. That is the repo's dominant bug class — a producer with no caller (A17) — in
# the very sensor built to detect mechanisms nobody wired. tests/test_sensor_is_read.py guards it.
_SENSOR_LOG = _REPO / ".claude" / "homunculus" / (_REPO.name or "default") / "sensor.jsonl"

# The tool is named `Agent`. `Task` is kept only because an older harness used it and a reader that
# silently misses a rename is the failure this file exists to prevent.
_AGENT_TOOLS = ("Agent", "Task")


def read() -> dict:
    """Aggregate every transcript. Returns counts; draws NO conclusion — that is the point."""
    agents: collections.Counter = collections.Counter()
    tools: collections.Counter = collections.Counter()
    tokens: collections.Counter = collections.Counter()
    sessions = 0

    if not _TRANSCRIPTS.exists():
        return {"transcripts_dir": str(_TRANSCRIPTS), "found": False, "sessions": 0,
                "agents": {}, "tools": {}, "tokens": {}}

    for f in sorted(_TRANSCRIPTS.glob("*.jsonl")):
        sessions += 1
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue                      # a sensor that raises is a sensor people delete
        for line in lines:
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            msg = d.get("message") or {}
            for k, v in (msg.get("usage") or {}).items():
                if isinstance(v, int):
                    tokens[k] += v
            for c in msg.get("content") or []:
                if not isinstance(c, dict) or c.get("type") != "tool_use":
                    continue
                tools[c.get("name")] += 1
                if c.get("name") in _AGENT_TOOLS:
                    agents[(c.get("input") or {}).get("subagent_type") or "(default)"] += 1

    return {"transcripts_dir": str(_TRANSCRIPTS), "found": True, "sessions": sessions,
            "agents": dict(agents), "tools": dict(tools), "tokens": dict(tokens)}


def declared_agents() -> list[str]:
    """The agents CLAUDE.md's Sub-agents table claims exist, from the files on disk."""
    return sorted(p.stem for p in (_REPO / ".claude" / "agents").glob("*.md"))


def read_injections(path: pathlib.Path = _INJECT_LOG) -> dict:
    """Count which domains inject_context.py loaded. `path` param keeps the test hermetic. Absence
    is NOT an error (same stance as read() on a missing transcript dir): the log accrues from the
    first keyword hit — no data means the sensor is new, not broken."""
    counts: collections.Counter = collections.Counter()
    dropped_counts: collections.Counter = collections.Counter()
    if not path.exists():
        return {"found": False, "prompts": 0, "domains": {}, "capped_prompts": 0,
                "dropped": {}, "rows_lost_to_rotation": 0}
    prompts = 0
    capped = 0
    rotated_away = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        # Rotation markers are accounting, not prompts — counted separately so a lifetime total is
        # never quietly reported as "since the last rotation".
        if d.get("event") == "rotation":
            rotated_away += int(d.get("rows_dropped") or 0)
            continue
        prompts += 1
        for dom in d.get("domains") or []:
            counts[dom] += 1
        # The CAP, surfaced. Writing `n_matched`/`dropped` without teaching the designated reader to
        # report them would manufacture a fresh `artefact-written-never-read` inside the fix for a
        # silent-truncation bug — the artefact→reader direction is the one that gets skipped.
        evicted = d.get("dropped") or []
        if evicted:
            capped += 1
            for dom in evicted:
                dropped_counts[dom] += 1
    return {"found": True, "prompts": prompts, "domains": dict(counts),
            "capped_prompts": capped, "dropped": dict(dropped_counts),
            "rows_lost_to_rotation": rotated_away}


def read_sensor(path: pathlib.Path = _SENSOR_LOG) -> dict:
    """Count SubagentStop rows by agent_type, plus tool failures. `path` keeps the test hermetic.

    Absence is NOT an error — same stance as read()/read_injections(). But `unknown` IS reported as
    its own number rather than folded into the total: a share computed over a population half of
    which is unattributable is a number nobody can defend, and hiding it would make this reader the
    thing it was built to catch."""
    agents: collections.Counter = collections.Counter()
    failures: collections.Counter = collections.Counter()
    keysets: collections.Counter = collections.Counter()
    if not path.exists():
        return {"found": False, "rows": 0, "agents": {}, "failures": {}, "unknown_keysets": {}}
    rows = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        rows += 1
        if d.get("event") == "SubagentStop":
            agents[d.get("agent") or "(unknown)"] += 1
            if d.get("payload_keys"):
                keysets[",".join(d["payload_keys"])] += 1
        elif d.get("event") == "PostToolUseFailure":
            failures[d.get("tool") or "(unknown)"] += 1
    return {"found": True, "rows": rows, "agents": dict(agents), "failures": dict(failures),
            "unknown_keysets": dict(keysets)}


def main() -> int:
    ap = argparse.ArgumentParser(description="What actually ran — read from Claude Code transcripts")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    data = read()
    inj = read_injections()
    sen = read_sensor()
    if args.json:
        print(json.dumps({**data, "injections": inj, "sensor": sen}, indent=2))
        return 0

    if not data["found"] or data["sessions"] == 0:
        # NO DATA IS NOT AN ERROR — and getting this wrong is how a guard gets disabled.
        # v2 exited 1 here. That was right for the repo this was born in (20 sessions) and WRONG
        # everywhere else: measured on the siblings, `immobilier` has no transcript dir at all and
        # `plugin_vst` has an empty one — Claude Code has simply never run there. Exiting 1 makes the
        # check permanently red on a healthy repo, which is the cry-wolf pattern this config keeps
        # getting bitten by (see test_claude_config.py's own comment on the book_frozen 🚨).
        # THE TOOL REPORTS; THE TEST JUDGES. A repo that must have data asserts it in its own suite
        # (`test_the_sensor_resolves`); a repo that has none is not broken, it is new.
        print(f"no agent data yet — {data['transcripts_dir']}\n"
              f"  Either Claude Code has never run in this repo, or the path derivation is wrong "
              f"(it flattens both '/' and '_' to '-'). Both look identical from here; check the dir.")
        return 0

    print(f"sensor: {data['sessions']} sessions — {data['transcripts_dir']}\n")

    declared = set(declared_agents())
    used = data["agents"]
    # `or 1` here would print "0/1 (0%) of traffic" on a repo with no agent calls — a denominator
    # nobody counted, reading as data. Measured on plugin_vst. Guard the division, not the truth.
    total = sum(used.values())
    print("AGENTS (all-time)")
    for name, n in sorted(used.items(), key=lambda kv: -kv[1]):
        tag = "declared" if name in declared else "BUILT-IN (absent from CLAUDE.md)"
        print(f"  {name:30s} {n:4d}   {tag}")
    dead = sorted(declared - set(used))
    for name in dead:
        print(f"  {name:30s} {0:4d}   🔴 DECLARED, NEVER INVOKED")
    builtin = sum(n for k, n in used.items() if k not in declared)
    share = f"{builtin}/{total} ({100 * builtin // total}%)" if total else "no agent calls recorded"
    print(f"\n  {len(dead)}/{len(declared)} declared agents never invoked · "
          f"{share} of traffic goes to built-ins" if total else
          f"\n  {len(dead)}/{len(declared)} declared agents never invoked · no agent calls recorded")

    # ORCHESTRATION — the ratio the roster table cannot show. `Agent` and `Workflow` are two
    # different mechanisms: an Agent call is one subagent, a Workflow call is a SCRIPT that fans out
    # to many. Measured 2026-07-27: 6 Workflow calls vs 190 Agent calls all-time, and all 6 passed an
    # INLINE script (persisted only to an ephemeral session dir, then lost — one of them was literally
    # named `engineering-loop-run`). That is why the loop now lives as a file: the tool was not
    # unused because it was unhelpful, it was unused because each use cost re-authoring 9-15 KB.
    n_wf = data["tools"].get("Workflow", 0)
    n_ag = sum(data["tools"].get(t, 0) for t in _AGENT_TOOLS)
    print("\nORCHESTRATION (tool calls, all-time)")
    print(f"  {'Agent/Task':30s} {n_ag:4d}   one subagent per call")
    print(f"  {'Workflow':30s} {n_wf:4d}   a SCRIPT that fans out to many")

    print("\nSUBAGENTS (in-repo sensor — hooks/sensor.py, SubagentStop)")
    if not sen["found"] or sen["rows"] == 0:
        print("  no rows yet — sensor.jsonl accrues from the first SubagentStop (sensor added "
              "2026-07-17).")
    else:
        sub_total = sum(sen["agents"].values())
        for name, n in sorted(sen["agents"].items(), key=lambda kv: -kv[1]):
            note = ""
            if name == "workflow-subagent":
                note = "   ← spawned BY a Workflow script; invisible to the transcripts above"
            elif name == "(unknown)":
                note = "   ← payload carried no agent_type; see unknown_keysets in --json"
            print(f"  {name:30s} {n:4d}{note}")
        unk = sen["agents"].get("(unknown)", 0)
        pct = f"{100 * unk // sub_total}%" if sub_total else "n/a"
        print(f"\n  {sub_total} SubagentStop row(s) · {unk} unattributed ({pct}) — "
              f"a share over a population this unattributed is not a number to quote")
        if sen["unknown_keysets"]:
            print("  payload key-sets seen on unattributed rows (names only, never values):")
            for ks, n in sorted(sen["unknown_keysets"].items(), key=lambda kv: -kv[1])[:5]:
                print(f"    {n:4d}  {ks}")
        if sen["failures"]:
            top = sorted(sen["failures"].items(), key=lambda kv: -kv[1])
            print(f"  tool failures recorded: {sum(sen['failures'].values())} — "
                  + ", ".join(f"{k} {v}" for k, v in top[:5]))

    print("\nTOKENS (all-time)")
    for k, v in sorted(data["tokens"].items(), key=lambda kv: -kv[1]):
        print(f"  {k:28s} {v:>16,}")
    print("\n  (tokens, not euros — a rate I have not measured would be a number nobody computed)")

    print("\nINJECTIONS (skills/rules/workflows auto-loaded by inject_context.py)")
    if not inj["found"] or inj["prompts"] == 0:
        print("  no injections recorded yet — inject.jsonl accrues from the first keyword hit "
              "(sensor added 2026-07-19).\n"
              "  A workflow is an INJECTION, not an agent call: this is how engineering-loop's\n  "
              "trigger-rate becomes measurable the way code-critic's "
              "invocations already are.")
    else:
        for name, n in sorted(inj["domains"].items(), key=lambda kv: -kv[1]):
            print(f"  {name:30s} {n:4d}")
        print(f"\n  {inj['prompts']} prompt(s) triggered an injection")
        # The CAP. A prompt that matched more domains than _MAX_DOMAINS lost the surplus silently
        # until 2026-07-27; rows written before then carry no `dropped` key and are simply absent
        # from these totals rather than counted as zero.
        if inj.get("capped_prompts"):
            print(f"  ⚠️ {inj['capped_prompts']} prompt(s) hit the _MAX_DOMAINS cap — these files "
                  f"matched but were NOT injected:")
            for name, n in sorted(inj["dropped"].items(), key=lambda kv: -kv[1]):
                print(f"     dropped {name:26s} {n:4d}")
        if inj.get("rows_lost_to_rotation"):
            print(f"  ⚠️ {inj['rows_lost_to_rotation']} row(s) dropped by log rotation — the counts "
                  f"above are since then, not lifetime.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
