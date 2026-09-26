"""`send_consolidated_alert` never ends a night without sending a mail.

Type: Sub
Uses: airflow/dags/alert_monitor.py (read as AST — never imported, it needs Airflow)
Depends on: nothing
Persists in: nothing

R181 (2026-09-26). The quiet-night branch used to `return` without a mail, and so did a
night whose findings repeated the last mail. The owner reads no automated mail, so the
only way the monitor's silence can MEAN something is if it never falls silent: every exit
now sends at least the short recap. code-critic noted this branch had no test before R181
changed it; this is that test.
"""
from __future__ import annotations

import ast
from pathlib import Path

_DAG = Path(__file__).resolve().parents[1] / "airflow" / "dags" / "alert_monitor.py"
_SENDS = {"_send_recap", "deliver_or_raise"}


def _sends(stmt: ast.AST) -> bool:
    return any(isinstance(n, ast.Call) and getattr(n.func, "id", "") in _SENDS
               for n in ast.walk(stmt))


def silent_exits(fn: ast.FunctionDef) -> list[int]:
    """Lines of the `return`s of `fn` (its own body — nested helpers excluded) that no
    earlier statement of the same block sends a mail before. Pure."""
    out = []

    def visit(stmts: list) -> None:
        for i, st in enumerate(stmts):
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(st, ast.Return) and not any(_sends(s) for s in stmts[:i]):
                out.append(st.lineno)
            for field in ("body", "orelse", "finalbody"):
                inner = getattr(st, field, None)
                if isinstance(inner, list):
                    visit(inner)
            for h in getattr(st, "handlers", []) or []:
                visit(h.body)

    visit(fn.body)
    return out


def _function(source: str, name: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.FunctionDef) and n.name == name)


def test_every_exit_of_the_nightly_mail_sends_one() -> None:
    fn = _function(_DAG.read_text(encoding="utf-8"), "send_consolidated_alert")
    silent = silent_exits(fn)
    assert not silent, (
        f"`send_consolidated_alert` sort sans mail aux lignes {silent}. Une nuit sans mail se "
        "lit comme un moniteur mort ; envoyer au moins `_send_recap(...)` avant de sortir.")
    assert _sends(fn), "the function no longer sends anything — the scan reads nothing"


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: the pre-R181 quiet branch (record, log, return) is a silent exit; the
    same branch sending the recap first is not; a `return` inside a nested helper is
    not the function's exit."""
    old = ("def send_consolidated_alert():\n"
           "    if not has_issues:\n"
           "        _close_alert_attempt(_record_quiet_run(), delivered=True, error=None)\n"
           "        logger.info('no alert sent')\n"
           "        return\n"
           "    deliver_or_raise(subject, body)\n")
    assert silent_exits(_function(old, "send_consolidated_alert")) == [5]
    new = old.replace("        _close_alert_attempt(_record_quiet_run(), delivered=True, error=None)\n",
                      "        _send_recap('nuit calme')\n")
    nested = ("def send_consolidated_alert():\n"
              "    def _helper():\n        return 1\n"
              "    deliver_or_raise(subject, body)\n")
    assert silent_exits(_function(new, "send_consolidated_alert")) == []
    assert silent_exits(_function(nested, "send_consolidated_alert")) == []
