"""R685 — a nightly mail the R572 pause withheld is never recorded as delivered.

Type: Guard
Uses: src/utils/email_alerts.py (deliver_or_raise), airflow/dags/alert_monitor.py
      (_close_after_send, _close_alert_withheld, _close_alert_attempt — compiled from the
      AST with a fake PostgresHandler; send_consolidated_alert read as AST)
Persists in: nothing (the SQL is captured, never run)

Measured 2026-11-01 in production: 18 nights since the pause (2026-10-15) sat in
`monitoring_run` with `delivered = TRUE` while no mail left. `deliver_or_raise` returned
None on a send AND on a pause, and both callers closed the row as delivered. The cost:
`_last_delivered_digest` (`WHERE delivered`) took a night nobody received for the last
mail read, so the first alert after the pause lifts could be shortened to « inchangé
depuis le mail du X ».

Mutation record (2026-11-01): `deliver_or_raise` returning None on pause → red;
`_close_after_send` ignoring `withheld` → red; a caller passing `None` instead of the
result → red; `delivery_expected` left TRUE in the withheld UPDATE → red.
"""
from __future__ import annotations

import ast
import logging
import sys
import types
from pathlib import Path

import pytest

from src.utils import email_alerts, ops_mail_pause

_DAG = Path(__file__).resolve().parents[1] / "airflow" / "dags" / "alert_monitor.py"
_LEDGER = ("_close_alert_attempt", "_close_alert_withheld", "_close_after_send")


class _Db:
    issued: list[tuple[str, tuple]] = []

    @classmethod
    def from_env_or_config(cls) -> "_Db":
        return cls()

    def execute_query(self, sql: str, params: tuple) -> None:
        _Db.issued.append((" ".join(sql.split()), params))

    def close(self) -> None: ...


@pytest.fixture
def ledger(monkeypatch) -> dict:
    """The three ledger functions of the DAG, bound to a recording handler."""
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in _LEDGER]
    assert {f.name for f in fns} == set(_LEDGER), "a ledger function was renamed or removed"
    fake = types.ModuleType("src.database.postgres_handler")
    fake.PostgresHandler = _Db
    monkeypatch.setitem(sys.modules, "src.database.postgres_handler", fake)
    _Db.issued = []
    ns = {"logger": logging.getLogger("t"), "safe_error": str}
    exec(compile(ast.Module(body=fns, type_ignores=[]), str(_DAG), "exec"), ns)  # noqa: S102
    return ns


def test_a_withheld_mail_is_neither_delivered_nor_expected(ledger) -> None:
    ledger["_close_after_send"](7, "owner ops mails paused (R572)", "sujet")
    (sql, params), = _Db.issued
    assert "delivered = FALSE" in sql and "delivery_expected = FALSE" in sql, sql
    assert params[-1] == 7 and "R572" in params[0], params


def test_a_mail_that_left_is_still_recorded_delivered(ledger) -> None:
    ledger["_close_after_send"](7, None, "sujet")
    (sql, params), = _Db.issued
    assert "SET delivered = %s" in sql and params == (True, None, 7), (sql, params)


def test_deliver_or_raise_names_the_pause_and_returns_none_on_a_send(monkeypatch) -> None:
    monkeypatch.setattr(email_alerts.EmailAlert, "_outbound_blocked", lambda self: None)
    monkeypatch.setattr(ops_mail_pause, "OPS_MAIL_PAUSED", True)
    monkeypatch.setattr(email_alerts, "paused_reason", ops_mail_pause.paused_reason)
    reason = email_alerts.deliver_or_raise("sujet", "corps")
    assert reason and "R572" in reason, reason
    monkeypatch.setattr(ops_mail_pause, "OPS_MAIL_PAUSED", False)
    monkeypatch.setattr(email_alerts.EmailAlert, "send_alert", lambda self, s, b: True)
    assert email_alerts.deliver_or_raise("sujet", "corps") is None


def _sends_pass_their_result(fn: ast.FunctionDef) -> list[int]:
    """Lines where `deliver_or_raise(...)` is called but its result does not reach
    `_close_after_send` in the same function body. Pure."""
    bound, passed, calls = set(), set(), []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "deliver_or_raise":
            calls.append(node.lineno)
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and getattr(node.value.func, "id", "") == "deliver_or_raise"):
            bound |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_close_after_send":
            passed |= {a.id for a in node.args if isinstance(a, ast.Name)}
    return calls if not (bound & passed) else []


def test_both_nightly_sends_hand_their_outcome_to_the_ledger() -> None:
    fn = next(n for n in ast.parse(_DAG.read_text(encoding="utf-8")).body
              if isinstance(n, ast.FunctionDef) and n.name == "send_consolidated_alert")
    nested = [n for n in ast.walk(fn) if isinstance(n, ast.FunctionDef)]
    recap = next(n for n in nested if n.name == "_send_recap")
    for scope in (recap, fn):
        assert not _sends_pass_their_result(scope), (
            f"`{scope.name}` calls deliver_or_raise without handing its result to "
            "_close_after_send — a withheld mail would be recorded delivered (R685)")
    assert sum(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "deliver_or_raise"
               for n in ast.walk(fn)) == 2, "the scan no longer sees both sends"


def test_the_scan_sees_a_discarded_outcome() -> None:
    bad = ("def f():\n    withheld = deliver_or_raise(s, b)\n"
           "    _close_after_send(run_id, None, s)\n")
    good = bad.replace("None", "withheld")
    parse = lambda src: ast.parse(src).body[0]  # noqa: E731
    assert _sends_pass_their_result(parse(bad)) == [2]
    assert _sends_pass_their_result(parse(good)) == []
