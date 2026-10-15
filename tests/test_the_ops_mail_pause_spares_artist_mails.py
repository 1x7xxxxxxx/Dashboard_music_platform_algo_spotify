"""R572 — the ops-mail pause silences the owner's alerts, never an artist's mail.

Type: Guard
Uses: src/utils/ops_mail_pause.py, src/utils/email_alerts.py, tools/dev/mail_red_verdict.py,
      tools/notify_schema_drift.py
Persists in: nothing (SMTP replaced by a recorder)

Owner, 2026-10-15: the ops mails are noise until an artist uses the app. A pause that
also stopped the verification mail would lock every new artist out — so both sides are
pinned: paused, no SMTP connection opens for an alert; an artist mail and the
account-deletion request still leave.
"""
from __future__ import annotations

import sys
from email.message import EmailMessage

import pytest

from src.utils import email_alerts, ops_mail_pause


class _Smtp:
    opened: list[str] = []

    def __init__(self, host, port, timeout=None) -> None:
        _Smtp.opened.append(host)

    def __enter__(self):
        return self

    def __exit__(self, *a) -> None:
        return None

    def starttls(self, **k) -> None: ...
    def login(self, *a) -> None: ...
    def send_message(self, *a, **k) -> None: ...
    def sendmail(self, *a, **k) -> None: ...


@pytest.fixture
def paused(monkeypatch):
    monkeypatch.setattr(ops_mail_pause, "OPS_MAIL_PAUSED", True)
    _Smtp.opened = []
    monkeypatch.setattr(email_alerts.smtplib, "SMTP", _Smtp)
    monkeypatch.setattr(email_alerts.EmailAlert, "_outbound_blocked", lambda self: None)
    for k, v in {"SMTP_USER": "u", "SMTP_PASSWORD": "p", "ALERT_EMAIL": "o@x.fr",
                 "SMTP_HOST": "smtp.test"}.items():
        monkeypatch.setenv(k, v)
    return _Smtp.opened


def test_the_switch_ships_paused() -> None:
    import importlib
    assert importlib.reload(ops_mail_pause).OPS_MAIL_PAUSED is True, (
        "R572 — the owner paused the ops mails until the app has a live artist")


def test_paused_an_ops_alert_opens_no_smtp(paused) -> None:
    alert = email_alerts.EmailAlert()
    assert alert.send_alert("x", "y") is False
    assert "R572" in (alert.last_error or "")
    email_alerts.deliver_or_raise("x", "y")          # no AlertDeliveryError
    email_alerts.dag_failure_callback({"dag": type("D", (), {"dag_id": "d"})()})
    assert paused == []


def test_paused_the_deletion_request_still_leaves(paused) -> None:
    assert email_alerts.EmailAlert().send_alert("x", "y", essential=True) is True
    assert paused == ["smtp.test"]


def test_paused_an_artist_mail_still_leaves(paused, monkeypatch) -> None:
    monkeypatch.setattr(email_alerts, "_artist_mail_opted_in", lambda: True)
    email_alerts.EmailAlert().send_email("artist@x.fr", "s", "<p>h</p>")
    assert paused == ["smtp.test"]


def test_paused_the_github_red_verdict_opens_no_smtp(paused, monkeypatch) -> None:
    sys.path.insert(0, "tools/dev")
    import mail_red_verdict
    monkeypatch.setattr(mail_red_verdict.smtplib, "SMTP", _Smtp)
    msg = EmailMessage()
    msg["Subject"] = "s"
    assert mail_red_verdict.send({"SMTP_HOST": "smtp.test"}, msg) is False
    assert mail_red_verdict.main() == 0
    assert paused == []


def test_paused_the_schema_drift_mail_opens_no_smtp(paused, monkeypatch) -> None:
    sys.path.insert(0, "tools")
    import notify_schema_drift
    monkeypatch.setattr(notify_schema_drift.smtplib, "SMTP", _Smtp)
    monkeypatch.setattr(sys, "argv", ["notify_schema_drift.py", "--subject", "s"])
    assert notify_schema_drift.main() == 0
    assert paused == []


def _senders_that_claim_success_unconditionally(source: str) -> list[int]:
    """Lines of a `send(...)` call used as a bare statement, its result dropped."""
    import ast
    return [n.lineno for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
            and getattr(n.value.func, "attr", getattr(n.value.func, "id", None)) == "send"]


def test_no_caller_says_sent_when_the_mail_was_paused() -> None:
    """R629 — nightly-recap run 38732548355 printed « ⏸️ not mailed » then « ✅ recap sent ».
    Every caller of the red-verdict `send()` must branch on its result."""
    from pathlib import Path
    hits = [f"{p}:{line}" for p in sorted(Path("tools/dev").glob("*.py"))
            if "mail_red_verdict" in (src := p.read_text(encoding="utf-8")) or p.name == "mail_red_verdict.py"
            for line in _senders_that_claim_success_unconditionally(src)]
    assert not hits, f"send() result dropped — its ✅ would lie while paused: {hits}"


def test_the_detector_sees_a_dropped_result_and_not_a_branch() -> None:
    assert _senders_that_claim_success_unconditionally("mail.send(env, m)\nprint('ok')\n") == [1]
    assert _senders_that_claim_success_unconditionally("if mail.send(env, m):\n    print('ok')\n") == []
