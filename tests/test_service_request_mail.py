"""R430 — the « Faire piloter » request leaves from the app, to the owner only.

Type: Guard
Uses: src.utils.service_request_mail
Depends on: nothing (SMTP replaced by a recorder)
Persists in: nothing
"""
from __future__ import annotations

import smtplib

import pytest

from src.utils import service_request_mail as m


class _Recorder:
    sent: list = []

    def __init__(self, *a, **k) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a) -> None:
        pass

    def starttls(self, **k) -> None:
        pass

    def login(self, *a) -> None:
        pass

    def send_message(self, msg) -> None:
        _Recorder.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    _Recorder.sent = []
    monkeypatch.setattr(smtplib, "SMTP", _Recorder)
    monkeypatch.setattr(m, "_smtp_config", lambda: {"user": "u", "password": "p"})
    return _Recorder.sent


def test_the_request_goes_to_the_fixed_address_with_the_artist_as_reply_to(smtp) -> None:
    assert m.send_service_request("owner@example.com", "Benken", "a@b.fr", "corps")
    (msg,) = smtp
    assert msg["To"] == "owner@example.com" and msg["Reply-To"] == "a@b.fr"
    assert msg["Subject"].endswith(f"{m.SUBJECT_PREFIX} — Benken")
    assert msg.get_payload(decode=True).decode() == "corps"


def test_a_header_value_cannot_carry_a_second_header(smtp) -> None:
    m.send_service_request("owner@example.com", "x\r\nBcc: victim@example.com",
                           "a@b.fr\r\nBcc: victim@example.com", "corps")
    (msg,) = smtp
    # What goes on the wire, not the object: `msg["Bcc"]` never sees an injected line.
    wire = msg.as_string().splitlines()
    assert not [x for x in wire if x.lower().startswith("bcc:")], wire[:8]


def test_no_smtp_means_false_not_a_crash(monkeypatch) -> None:
    monkeypatch.setattr(m, "_smtp_config", lambda: {})
    assert m.send_service_request("o@example.com", "x", "a@b.fr", "corps") is False
