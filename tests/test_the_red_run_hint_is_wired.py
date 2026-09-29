"""The Stop hook signals rule 12's threshold from the last suite — and main actually calls it.

Type: Sub
Uses: .claude/hooks/session_summary.py (red_run_hint, main)
Depends on: nothing — a scratch `.pytest-last.log`

R322 (2026-09-29): `run_pytest_summary` held the `failures >= 5` of CLAUDE.md rule 12 and
was never called (code-critic R315). It is replaced by a reader of `.pytest-last.log`, which
the test targets already write — and what is pinned is that `main` REACHES it.

Mutation record (2026-09-29): seen red with the call removed from `main`, and with the
threshold at `>= 6`.
"""
import ast
import importlib.util
import os
import time
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".claude/hooks/session_summary.py"
_spec = importlib.util.spec_from_file_location("session_summary", HOOK)
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)


def _log(root: Path, reds: int) -> None:
    body = [f"FAILED tests/test_x.py::t{i} - assert 0" for i in range(reds)]
    (root / ".pytest-last.log").write_text("\n".join(body + ["1 failed"]) + "\n")


def test_five_reds_name_the_agent_and_four_do_not(tmp_path) -> None:
    _log(tmp_path, 5)
    assert "build-error-resolver" in (ss.red_run_hint(str(tmp_path)) or "")
    _log(tmp_path, 4)
    assert ss.red_run_hint(str(tmp_path)) is None


def test_an_old_log_is_another_sessions_verdict(tmp_path) -> None:
    _log(tmp_path, 9)
    old = time.time() - 7200
    os.utime(tmp_path / ".pytest-last.log", (old, old))
    assert ss.red_run_hint(str(tmp_path)) is None


def test_main_reaches_the_hint() -> None:
    tree = ast.parse(HOOK.read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    called = {getattr(c.func, "id", None) for c in ast.walk(main) if isinstance(c, ast.Call)}
    assert "red_run_hint" in called, "the rule-12 signal is dead code again"
