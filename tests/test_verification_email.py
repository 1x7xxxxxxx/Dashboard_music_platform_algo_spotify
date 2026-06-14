"""Regression guards for transactional email HTML (verification + welcome).

Type: Utility (test)
Depends on: src/utils/verification_email

Captures the rendered HTML by intercepting the SMTP send, then asserts the CTA
buttons are robust across email clients. The button-overlap bug (2026-06-14): the
`<a>` CTA had vertical `padding` but no `display: inline-block`, so Gmail did not
expand the line box and the green button overlapped neighbouring text.
"""
import smtplib

import pytest

from src.utils import verification_email as ve


class _FakeSMTP:
    """Context-manager stand-in for smtplib.SMTP that records the sent message."""

    sent = []

    def __init__(self, *_a, **_k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def starttls(self):
        pass

    def login(self, *_a):
        pass

    def send_message(self, msg):
        _FakeSMTP.sent.append(msg)


def _html_of(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode("utf-8")
    raise AssertionError("no text/html part in message")


@pytest.fixture
def captured_emails(monkeypatch):
    """Send both transactional emails through a fake SMTP and return their HTML."""
    _FakeSMTP.sent = []
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "x")
    # No attachments needed; keep the welcome path from touching the filesystem.
    monkeypatch.setattr(ve, "_guide_pdf_paths", lambda: [])

    assert ve.send_verification_email("a@b.co", "Ada", "tok", lang="en") is True
    assert ve.send_welcome_email("a@b.co", "Ada", user_id=1, lang="en") is True
    return [_html_of(m) for m in _FakeSMTP.sent]


def test_cta_buttons_are_inline_block(captured_emails):
    """Every green CTA <a> must be display:inline-block so vertical padding expands
    the box instead of overlapping adjacent lines (the Gmail overlap bug)."""
    assert captured_emails, "no emails were sent"
    for html in captured_emails:
        # Each email has exactly one styled CTA anchor (background #1DB954).
        assert "padding: 14px 28px" in html
        # The anchor that carries the button padding must also be inline-block.
        assert "display: inline-block" in html, (
            "CTA button missing display:inline-block — vertical padding will overlap "
            "neighbouring text in Gmail (regression of the 2026-06-14 button bug)"
        )
