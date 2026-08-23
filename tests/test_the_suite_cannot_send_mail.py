"""
Guard — the boundary that stops a test from sending real email must actually bite.

Type: Sub
Uses: smtplib, pytest
Triggers: pytest
Depends on: tests/conftest.py::_no_real_smtp
Persists in: nothing

Error class: test-sends-real-mail-to-real-people.

Measured 2026-08-23. `test_admin_hypeddit_buttons.py` presses every button on the admin
view; one of them is `📧 Renvoyer vérification`, which calls `send_verification_email`
with an address read from the database the run points at. Locally that database is the
migrated copy of production and `.env` holds real Gmail credentials, so three suite runs
delivered three real verification emails — each carrying `http://localhost:8501` because
no local process sets APP_BASE_URL. There was no network boundary in `conftest.py` at
all.

This file is the SIGNATURE of that class, and it needs no database: it trips the
boundary on purpose and checks both halves — that the connection is refused, and that
the attempt is RECORDED. The recording is the half that matters, because
`send_verification_email` wraps its send in `except Exception`: an exception alone is
swallowed and the offending test stays green. Only the teardown assertion, which the
application's error handling cannot reach, turns it red.
"""

import smtplib

import pytest


def test_a_test_cannot_open_a_real_smtp_connection(request) -> None:
    with pytest.raises(ConnectionRefusedError):
        smtplib.SMTP("smtp.example.invalid", 25)

    attempts = getattr(request.node, "_smtp_attempts", None)
    assert attempts == ["smtp.example.invalid:25"], (
        "the SMTP boundary refused the connection but did not RECORD it — an "
        "application that swallows the exception would leave the offending test green"
    )
    # Consumed: this test meant to trip the boundary, so it must not fail at teardown.
    attempts.clear()


def test_the_ssl_variant_is_blocked_too(request) -> None:
    with pytest.raises(ConnectionRefusedError):
        smtplib.SMTP_SSL("smtp.example.invalid", 465)
    request.node._smtp_attempts.clear()
