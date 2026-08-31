"""Reaching an artist by email requires an explicit yes, not a data coincidence.

Asked on 2026-08-31, on seeing `[Benken] Weekly KPI` in the admin inbox:
« comment ça les artistes reçoivent des mails ? Je n'ai pas encore validé ».

They had not. Measured that day:

  * the weekly digest sends one message PER TENANT but every one of them to
    `ALERT_EMAIL` — the subject NAMES the tenant, it does not address them. The
    2026-08-31 run logged `7/7 emails sent`, all to the operator;
  * `onboarding_report` — the only caller of `EmailAlert.send_email`, the only
    path with a tenant address in `To:` — had never fired for an artist:
    `onboarding_report_sent_at` was NULL for all seven, set only for the admin.

That second one held for a reason nobody chose. The DAG defers until the artist
has S4A rows, and exactly one tenant has any. **The first artist to upload a CSV
would have been mailed a PDF report the next morning at 09:00, unprompted.**

Pausing the DAG was the immediate fix, and a pause lives in Airflow's own
database: a `--force-recreate`, a restore, or one click in the UI undoes it and
nothing anywhere records that it happened. This pins the durable half — the
send itself is off unless someone turned it on.

What is deliberately NOT gated: `verification_email`, which an artist triggers by
signing up. Consent is the difference, not the recipient.
"""
from __future__ import annotations

import pytest

from src.utils.email_alerts import _ARTIST_MAIL_OPT_IN, EmailAlert


@pytest.fixture
def wired(monkeypatch):
    """Record every SMTP construction; reaching it means the message went out."""
    seen = []

    class _Recorder:
        def __init__(self, *a, **k):
            seen.append(a)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, *a, **k):
            pass

        def login(self, *a, **k):
            pass

        def send_message(self, *a, **k):
            pass

        def sendmail(self, *a, **k):
            pass

        def quit(self):
            pass

    import smtplib
    monkeypatch.setattr(smtplib, "SMTP", _Recorder)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _Recorder)
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("ALERT_EMAIL", "admin@example.com")
    monkeypatch.setenv("STREAMLYTICS_ENV", "production")
    monkeypatch.delenv(_ARTIST_MAIL_OPT_IN, raising=False)
    return seen


def test_production_alone_does_not_authorise_writing_to_an_artist(wired):
    """The instance being real is not the same question as the audience being ours."""
    sent = EmailAlert().send_email("artiste@example.com", "ton rapport", "<p>x</p>")

    assert sent is False, (
        "a correct production instance mailed a tenant with nobody having opted in. "
        f"Set {_ARTIST_MAIL_OPT_IN}=1 to authorise it — the point is that it is a "
        "decision someone takes, not a default."
    )
    assert not wired, "the message reached SMTP despite the gate"


def test_the_operator_channel_is_untouched(wired):
    """Silencing artist mail must not silence the alerts — a mute monitor is the incident."""
    assert EmailAlert().send_alert("panne réelle", "<p>x</p>") is True, (
        "the artist-audience gate leaked onto send_alert, which only ever reaches "
        "ALERT_EMAIL. An alert that cannot be delivered IS the incident."
    )
    assert len(wired) == 1


def test_an_explicit_yes_lets_it_through(wired, monkeypatch):
    monkeypatch.setenv(_ARTIST_MAIL_OPT_IN, "1")

    assert EmailAlert().send_email("artiste@example.com", "ton rapport", "<p>x</p>") is True
    assert len(wired) == 1, "the explicit opt-in did not let the message through"


@pytest.mark.parametrize("vague", ["", "0", "no", "maybe", "false", " "])
def test_a_vague_value_is_not_a_yes(wired, monkeypatch, vague):
    """A half-configured environment stays silent rather than guessing."""
    monkeypatch.setenv(_ARTIST_MAIL_OPT_IN, vague)

    assert EmailAlert().send_email("artiste@example.com", "ton rapport", "<p>x</p>") is False, (
        f"{vague!r} was read as an authorisation to write to a client"
    )
    assert not wired
