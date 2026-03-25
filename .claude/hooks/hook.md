# Hooks Documentation

All hooks configured in `.claude/settings.json`. Scripts in `.claude/hooks/`.

---

## Active Hooks

### 1. UserPromptSubmit → `inject_context.py`

| Property | Value |
|---|---|
| Event | `UserPromptSubmit` |
| Script | `.claude/hooks/inject_context.py` |
| Input | `{session_id, transcript_path, prompt}` via stdin (JSON) |
| Output | Printed context block (stdout) injected before Claude reads the prompt |
| Exit code | Always `0` — never blocking |

**Logic**: Reads the user's prompt text. Detects domain keywords via regex. Prints the relevant skill content as a `<system-reminder>` block.

| Keyword detected | Skill injected |
|---|---|
| "dashboard", "view", "streamlit" | `.claude/skills/dashboard-view.md` patterns |
| "dag", "airflow", "collector" | `.claude/skills/airflow-dag.md` patterns |
| "schema", "upsert", "postgres" | `.claude/skills/db-schema.md` patterns |

---

### 2. PostToolUse → `check_python_syntax.py`

| Property | Value |
|---|---|
| Event | `PostToolUse` |
| Matcher | `Write` or `Edit` on `.py` files |
| Script | `.claude/hooks/check_python_syntax.py` |
| Input | `{tool_name, tool_input.file_path}` via stdin (JSON) |
| Output | Lint warnings printed to stdout |
| Exit code | `2` on E9 syntax errors (blocking), `0` otherwise |

**Logic**: Runs `ruff` (preferred) or falls back to `py_compile`. E9 errors (SyntaxError) exit 2, which blocks Claude and forces an immediate fix. F-series warnings (pyflakes) are informational only.

---

### 3. Stop → `session_summary.py`

| Property | Value |
|---|---|
| Event | `Stop` |
| Script | `.claude/hooks/session_summary.py` |
| Input | `{session_id, transcript_path, stop_hook_active}` via stdin (JSON) |
| Output | Summary printed to stdout (shown as system context) |
| Exit code | Always `0` — never blocking |

**Logic** (4 sequential steps):
1. **Git changes** — `git status --short`, skips `.pyc`/`__pycache__`/`mlruns`, shows up to 15 files
2. **Docker health** — checks 3 containers: `postgres_spotify_airflow`, `airflow_scheduler`, `airflow_webserver`
3. **Session length** — counts assistant turns in transcript; warns at ≥20 turns
4. **Pytest summary** — runs `pytest tests/ --tb=no -q` with 60s timeout; signals if ≥5 failures

**Stop-hook loop guard**: Step 4 skips if `stop_hook_active = true` to prevent infinite re-triggering.

---

## Exit Code Reference

| Code | Effect | When to use |
|---|---|---|
| `0` | Continue. stdout shown as context to Claude | Informational hooks (always use for Stop) |
| `2` | Block the action. stderr/stdout shown to Claude | Hard validation failures (syntax errors) |

**Never exit `1`** — reserved for unexpected errors, behavior is undefined.

---

## Adding a New Hook

1. Write the script in `.claude/hooks/<name>.py`
   - Read JSON from `sys.stdin`
   - Print output to `stdout`
   - Exit `0` (informational) or `2` (blocking)
2. Register in `.claude/settings.json`:
```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "optional_tool_matcher",
        "hooks": [
          { "type": "command", "command": "python3 .claude/hooks/<name>.py" }
        ]
      }
    ]
  }
}
```
3. Document the new hook in this file (event, input, output, exit code, logic)

---

## Current `settings.json` Structure

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "python3 .claude/hooks/inject_context.py" }] }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [{ "type": "command", "command": "python3 .claude/hooks/check_python_syntax.py" }]
      }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "python3 .claude/hooks/session_summary.py" }] }
    ]
  }
}
```
