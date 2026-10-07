"""R449 — night-check names the agent worktrees left behind for more than 48 h.

Type: Sub
Uses: tools/dev/night_run.py (stale_worktrees, cmd_check)
Depends on: nothing — worktree ages are fabricated

15 merged, dirty worktrees piled up under `.claude/worktrees/` and nothing said so.
"""
import ast
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("night_run_r449", _ROOT / "tools/dev/night_run.py")
nr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nr)


def test_only_worktrees_past_the_limit_are_named() -> None:
    trees = [("/r/.claude/worktrees/agent-old", 49.0), ("/r/.claude/worktrees/agent-new", 47.0)]
    (msg,) = nr.stale_worktrees(trees)
    assert msg.startswith("1 worktree(s)") and "agent-old" in msg and "agent-new" not in msg
    assert nr.stale_worktrees([("/r/wt", 47.9)]) == []
    assert nr.stale_worktrees([]) == []


def test_night_check_reports_them() -> None:
    fn = next(n for n in ast.parse((_ROOT / "tools/dev/night_run.py").read_text()).body
              if isinstance(n, ast.FunctionDef) and n.name == "cmd_check")
    called = {c.func.id for c in ast.walk(fn) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert {"stale_worktrees", "_worktrees"} <= called
