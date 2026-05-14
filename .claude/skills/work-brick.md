---
name: work-brick
description: "Autonomous brick iteration. Invoke as /work-brick <B-ID>. Executes one atomic step per turn on a roadmap brick, self-paces via ScheduleWakeup(60s), stops on brick done, pytest red, no-progress, iteration cap, or context critical. Zero remote API cost — runs only while the local session is active."
risk: medium
source: project
date_added: "2026-04-20"
rex: []
---

# /work-brick — autonomous brick iteration

Pilots a single brick from ROADMAP/BRICKS.md to completion, one atomic step per turn. State persists across `/clear` via `.claude/sessions/brick_session.json`.

## Invocation

```
/work-brick B59
```

Optional args: `max=<N>` (default 30 iterations), `dry-run` (print plan, no edits).

## Each iteration — DO EXACTLY THIS

Run steps 1-8 in order. Do **not** skip, do **not** batch-plan ahead, do **not** explore unrelated files.

### 1. Load state

```python
from tools.brick_state import load_state, new_state, save_state, find_repo_root
root = find_repo_root()
state = load_state(root) or new_state("<B-ID>")
```

If `state["status"] != "running"` → do not relaunch. Print the status + blocker_reason and stop.

### 2. Pre-flight guards

- `state["iterations"] >= state["max_iterations"]` → `mark_paused(state, "iteration cap reached")`, save, stop.
- Any CRITICAL from `context_monitor.py` in the last tool output → flush `working_tree_snapshot(root)` into state, save, message: *"Context critical — /clear, session_start.py will propose resumption."* Do NOT ScheduleWakeup.

### 3. Read the brick entry

Grep `.claude/dev-docs/BRICKS.md` for the brick ID row. Parse:
- Status emoji (✅ done, 🟡 WIP, 🔵 ready, ⚪/❌ blocked).
- `Prochain:` field (plain-text next step).

If status is already ✅ → `mark_done(state)`, save, stop.
If `Prochain:` is empty or ambiguous → `mark_paused(state, "next step undefined — /dev-docs <brick> needed")`, save, stop.

### 4. Execute ONE atomic step

The step from `Prochain:`. Scope = one logical change:
- edit 1-3 files OR
- add 1 helper + its test OR
- update 1 doc section.

**Do not expand scope.** If the step looks too big, split it mentally and do only the first substep — then update `Prochain:` in BRICKS.md with the remainder.

### 5. Run targeted tests

```bash
cd src/Application && python3 -m pytest tests/ -q --tb=short
```

Prefer a narrower path if the step touches a known module (e.g. `tests/test_api.py`).

Parse the summary line. Store `{"passed": N, "failed": M, "at": "<iso>"}` in `state["tests_last_run"]`.

### 6. Gate on pytest

If `failed > 0`:
```python
mark_blocked(state, f"pytest {failed} failed: <last_line>")
save_state(state)
```
Stop. Do NOT ScheduleWakeup. Do NOT attempt auto-fix.

### 7. Progress check + trackers

```python
from tools.brick_state import progress_hash, working_tree_snapshot, is_stalled, increment_iteration

files = [<files touched this iteration>]
new_hash = progress_hash(files, "<step name>")
if is_stalled(state, new_hash):
    mark_blocked(state, "no progress — same step hash twice")
    save_state(state); stop
state["last_progress_hash"] = new_hash
state["last_step"] = "<step name>"
state["working_tree_snapshot"] = working_tree_snapshot(root)
increment_iteration(state)
```

If the step closed the brick (Prochain: empty + all deliverables done):
- Flip status to ✅ in BRICKS.md summary table.
- Move narrative block to "Completed Bricks" section.
- Append DEVLOG.md entry (Why / What changed / Tests — use real pytest count from step 5).
- Append `.claude/dev-docs/archives/retro.md` line: `YYYY-MM-DD HH:MM — <brick done> | — | — | —`.
- `mark_done(state)`, save, stop.

Otherwise update the brick's `Prochain:` field with the next atomic step (from the detail/archive link) and persist `save_state(state)`.

### 8. Reschedule

Only if `state["status"] == "running"` after all guards:

```
ScheduleWakeup(delaySeconds=60, prompt="/work-brick <B-ID>",
               reason="brick <id> iteration <n+1> — next step: <step>")
```

## Hard rules (non-negotiable)

- **No commits.** Working tree only. Commits are user-driven.
- **No destructive ops** (push, force, rm -rf, migration prod). If a step requires one → `mark_paused`, ask for human.
- **No scope creep.** If you notice unrelated tech debt, ignore it — not this brick's job.
- **Python rules** (`.claude/rules/python.md`) apply to any edit: type hints, no bare except, no f-strings in SQL, 40 line function cap.
- **Test rules** (`.claude/rules/tests.md`) apply to new tests: no DB mocking, no hardcoded thresholds, one behavior per test.
- **API rules** (`.claude/rules/api.md`) apply to any new endpoint: Pydantic response_model, 503 on model fail, endpoint added to `.claude/dev-docs/api/endpoints.md`.

## Resumption after /clear

`session_start.py` auto-injects a resume suggestion when `brick_session.json.status == "running"`. User hits Enter → `/work-brick <B-ID>` relaunches where it left off. No state is lost (snapshot in `working_tree_snapshot` gives visibility on the pending diff).

## Stopping manually

User types anything else → ScheduleWakeup is NOT re-fired, loop dies naturally. State remains `running` until the user runs `/work-brick <B-ID>` again or edits state to `paused`.
