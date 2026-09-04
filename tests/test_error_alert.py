"""Tests for the app-error notifier (C1) — fail-silent + control-flow passthrough."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dashboard.utils import error_alert  # noqa: E402


# Class names must match Streamlit's exactly — is_control_flow keys on __name__.
class RerunException(Exception):
    pass


class StopException(Exception):
    pass


def test_is_control_flow_detects_streamlit_signals():
    assert error_alert.is_control_flow(RerunException("x")) is True
    assert error_alert.is_control_flow(StopException("x")) is True
    assert error_alert.is_control_flow(ValueError("x")) is False


def test_notify_app_error_never_raises(monkeypatch):
    # No SMTP configured → must still return cleanly (fail-silent telemetry).
    monkeypatch.setattr("src.utils.verification_email._smtp_config", lambda: {})
    error_alert.notify_app_error("somepage", ValueError("boom"))  # must not raise


def test_notify_app_error_skips_control_flow():
    # Control-flow signals are not errors → no email attempt, no raise.
    error_alert.notify_app_error("somepage", StopException("stop"))


def test_email_rate_limited(monkeypatch):
    """The IN-PROCESS cooldown, isolated from the registry.

    It broke on 2026-09-04 when the second, durable cooldown landed: `_email_due`
    reads `app_error_log`, this suite runs against a live database, and the previous
    run of this very test had left a `last_emailed_at` less than 15 minutes old. The
    test then asserted 1 and got 0 — correctly, and for a reason that had nothing to
    do with the code under test.

    A unit test of the in-process guard must not depend on rows a previous run wrote.
    `_record` is stubbed with a fresh fingerprint per call, which is also what makes
    the two layers separable at all.
    """
    import uuid

    sent = []
    monkeypatch.setattr("src.utils.verification_email._smtp_config",
                        lambda: {"user": "admin@example.com"})
    monkeypatch.setattr("src.utils.verification_email._send_html",
                        lambda *a, **k: sent.append(a) or True)
    monkeypatch.setattr(error_alert, "_record", lambda *a, **k: uuid.uuid4().hex)
    monkeypatch.setattr(error_alert, "_mark_emailed", lambda *a, **k: None)
    monkeypatch.setattr(error_alert, "_email_due", lambda *a, **k: True)
    error_alert._last_sent.clear()
    error_alert.notify_app_error("p", ValueError("boom"))
    error_alert.notify_app_error("p", ValueError("boom"))  # same signature → suppressed
    assert len(sent) == 1


def test_the_email_cooldown_survives_a_restart(monkeypatch):
    """The layer the in-process dict cannot provide.

    `_last_sent` lives in the process. Recreating the container re-sent the same alert,
    and that happened. `_email_due` reads `last_emailed_at` from the registry, so the
    cooldown outlives the process — and fails OPEN, because losing an alert to a
    database hiccup is worse than one duplicate.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    class _Db:
        def __init__(self, last):
            self._last = last

        def fetch_query(self, *a, **k):
            return [(self._last,)] if self._last is not None else []

        def close(self):
            pass

    def _with(last):
        monkeypatch.setattr("src.dashboard.utils.get_db_connection",
                            lambda *a, **k: _Db(last))
        return error_alert._email_due("f" * 40, now)

    assert _with(now - timedelta(minutes=1)) is False, "a fresh send is not suppressed"
    assert _with(now - timedelta(hours=2)) is True, "an old send blocks for ever"
    assert _with(None) is True, "never emailed → must send"

    monkeypatch.setattr("src.dashboard.utils.get_db_connection",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert error_alert._email_due("f" * 40, now) is True, (
        "the cooldown fails CLOSED on a database error: an outage would silence every "
        "alert, which is the opposite of what an alerter is for."
    )
