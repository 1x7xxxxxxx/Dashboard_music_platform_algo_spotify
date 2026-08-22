"""An alert that was not delivered must never be logged as delivered.

Installed 2026-08-22, from production logs. `alert_monitor.py` ended with:

    EmailAlert().send_alert(subject, body)              # returns False, discarded
    logger.info(f"Consolidated alert sent: {subject}")  # unconditional

On the nights of 16, 17 and 18 August the scheduler wrote "Consolidated alert sent"
immediately after `email_alerts` warned "Email alerts non configurées". Three nights
of findings evaporated with a green task. The findings were computed correctly and
rendered correctly; the last hop was never checked.

`tests/test_alert_monitor_sends_what_it_finds.py` already guards the hop before this
one — that every finding takes part in the send DECISION. It cannot see this one,
because it never asks whether the send SUCCEEDED. The chain is:

    computed ✅ guarded → in the body ✅ guarded → in has_issues ✅ guarded
    → actually delivered ❌ was not guarded, and that is the link that broke.

The AST sweep at the bottom generalises it: any `send_alert` / `send_email` call whose
result is thrown away is the same defect waiting in another file.
"""
from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


# ── the wrapper's own contract ───────────────────────────────────────────────

def test_deliver_or_raise_raises_when_smtp_is_not_configured(monkeypatch):
    """The literal production condition of 16-18 August."""
    from src.utils import email_alerts

    for var in ("SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(email_alerts.AlertDeliveryError) as exc:
        email_alerts.deliver_or_raise("sujet", "<p>corps</p>")

    assert "not configured" in str(exc.value), (
        "the exception must name WHICH failure this is — an absent env var and a "
        "refused SMTP login have different fixes, and a bare False said neither"
    )


def test_deliver_or_raise_names_a_send_failure_differently(monkeypatch):
    from src.utils import email_alerts

    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")   # pragma: allowlist secret
    monkeypatch.setenv("ALERT_EMAIL", "a@b.c")

    class _Boom:
        def __init__(self, *a, **k):
            raise OSError("connection refused")

    monkeypatch.setattr(email_alerts.smtplib, "SMTP", _Boom)
    with pytest.raises(email_alerts.AlertDeliveryError) as exc:
        email_alerts.deliver_or_raise("sujet", "<p>corps</p>")
    assert "send failed" in str(exc.value)


def test_deliver_or_raise_is_silent_on_success(monkeypatch):
    """Non-vacuity: it must not raise on the happy path."""
    from src.utils import email_alerts

    monkeypatch.setattr(email_alerts.EmailAlert, "send_alert",
                        lambda self, s, b: True)
    email_alerts.deliver_or_raise("sujet", "<p>corps</p>")


def test_send_alert_stays_non_raising(monkeypatch):
    """Six callers depend on it, including a failure callback. Do not change it."""
    from src.utils import email_alerts

    for var in ("SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL"):
        monkeypatch.delenv(var, raising=False)
    assert email_alerts.EmailAlert().send_alert("s", "b") is False


def test_the_log_cannot_claim_a_delivery_that_did_not_happen(monkeypatch, caplog):
    """The exact shape of the incident: a warning, then a success line."""
    from src.utils import email_alerts

    for var in ("SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL"):
        monkeypatch.delenv(var, raising=False)

    with caplog.at_level(logging.INFO):
        with pytest.raises(email_alerts.AlertDeliveryError):
            email_alerts.deliver_or_raise("sujet", "corps")

    claimed = [r.getMessage() for r in caplog.records
               if "sent" in r.getMessage().lower() or "envoyée" in r.getMessage().lower()]
    assert not claimed, f"a delivery was claimed while it failed: {claimed}"


# ── the class sweep: no result may be discarded ──────────────────────────────

_SEND_METHODS = {"send_alert", "send_email", "deliver_or_raise"}
_SCANNED = [
    REPO / "airflow" / "dags",
    REPO / "airflow" / "debug_dag",
    REPO / "src" / "utils",
]
# `dag_failure_callback` runs INSIDE an Airflow failure callback, where a raise is
# swallowed by the scheduler anyway. Binding the result there would be theatre.
_EXEMPT = {("email_alerts.py", "dag_failure_callback")}


def _discarded_send_calls() -> list[str]:
    out = []
    for root in _SCANNED:
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if (path.name, fn.name) in _EXEMPT:
                    continue
                for node in ast.walk(fn):
                    # A bare expression statement — the result goes nowhere.
                    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                        continue
                    f = node.value.func
                    name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                    if name in _SEND_METHODS and name != "deliver_or_raise":
                        out.append(f"{path.relative_to(REPO)}:{node.lineno} "
                                   f"in {fn.name}() — {name}(...) result discarded")
    return out


def test_no_send_result_is_thrown_away():
    """Bind the result, or call `deliver_or_raise`. Never neither.

    This is the generalisation, not the instance. The defect was one line in one
    file; the shape — a boolean that says whether anyone was told, dropped on the
    floor — can appear in any of the four modules that send mail.
    """
    offenders = _discarded_send_calls()
    assert not offenders, (
        "a send result is discarded, so a failure there is invisible:\n  "
        + "\n  ".join(offenders)
        + "\nBind it and log an error, or use email_alerts.deliver_or_raise() when "
          "the silence of that message is itself the incident."
    )


def test_the_sweep_would_notice_a_discarded_call():
    """Non-vacuity: prove the AST walk actually finds this shape."""
    tree = ast.parse("def f():\n    EmailAlert().send_alert('a', 'b')\n")
    found = [n for n in ast.walk(tree)
             if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
             and getattr(n.value.func, "attr", "") == "send_alert"]
    assert found, "the walk does not recognise a discarded send_alert — it guards nothing"


def test_the_consolidated_alert_uses_the_raising_path():
    """The one path whose silence is the incident must be the one that raises."""
    src = (REPO / "airflow" / "dags" / "alert_monitor.py").read_text(encoding="utf-8")
    assert "deliver_or_raise(subject, body)" in src, (
        "send_consolidated_alert no longer goes through deliver_or_raise — a failed "
        "delivery would be silent again"
    )
