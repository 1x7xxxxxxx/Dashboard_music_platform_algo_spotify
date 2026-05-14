# Hook Reference — Claude Code

> TODO: Document each hook in .claude/hooks/ — event, purpose, exit codes, and configuration points.

| Hook file | Event | Effect | Exit codes |
|-----------|-------|--------|------------|
| session_start.py | SessionStart | Injects prior session context | 0 = ok |
| inject_context.py | UserPromptSubmit | Loads ≤3 skill files on keyword match | 0 = ok |
| guard_destructive.py | PreToolUse Bash | Blocks/warns dangerous commands | 2 = block, 0 = warn |
| pre_commit_scan.py | PreToolUse git commit | Blocks secrets + debug artifacts | 2 = block, 0 = warn |
| check_python_syntax.py | PostToolUse Write/Edit | ruff syntax check | 2 = block, 0 = warn |
| check_roadmap_update.py | PostToolUse Write/Edit | Reminds if ROADMAP stale | 0 = remind |
| observe.py | PostToolUse Write/Edit | Appends to observations.jsonl | 0 = ok |
| context_monitor.py | PostToolUse (all) | Warns at high turn count | 0 = warn |
| pre_compact.py | PreCompact | Saves session snapshot | 0 = ok |
| session_summary.py | Stop | Git + Docker + pytest summary | 0 = ok |

## Editing hooks

Edit `.claude/hooks/<name>.py` directly. Re-run `python3 -c "import ast; ast.parse(open('.claude/hooks/<name>.py').read())"` to validate syntax.
