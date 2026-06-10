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
    sent = []
    monkeypatch.setattr("src.utils.verification_email._smtp_config",
                        lambda: {"user": "admin@example.com"})
    monkeypatch.setattr("src.utils.verification_email._send_html",
                        lambda *a, **k: sent.append(a) or True)
    error_alert._last_sent.clear()
    error_alert.notify_app_error("p", ValueError("boom"))
    error_alert.notify_app_error("p", ValueError("boom"))  # same signature → suppressed
    assert len(sent) == 1
