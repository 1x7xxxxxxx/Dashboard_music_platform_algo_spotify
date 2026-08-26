"""A non-production instance must not send mail. Naming itself is not enough.

Third occurrence of one event, in three days:

  2026-08-23  a dev box shipped three real verification mails, `localhost` links,
              to real people. Fixed by an SMTP boundary IN THE TEST SUITE.
  2026-08-24  a local scheduler replayed a scheduled run and mailed a real inbox
              twice. Fixed by prefixing the subject with `[LOCAL]`.
  2026-08-26  a local scheduler mailed the same real inbox twice again, at 19:48,
              after a session restarted the local Postgres so the suite could run
              against a live database. The idle scheduler got its database back and
              replayed its runs. The `[LOCAL]` prefix worked perfectly — and the
              mails still arrived, still had to be opened, still had to be triaged.

The 2026-08-24 fix was a LABELLING fix for a SENDING problem, and the 2026-08-23 one
bounded the SUITE while the scheduler was never in scope. The cost of an unwanted
alert is paid on receipt. So the default is now silence off production.

The dangerous half of this change is the one asserted hardest below: a gate that
suppresses alerts must never be able to silence production. `STREAMLYTICS_ENV` is a
required variable for `airflow_scheduler` in `tools/check_env_parity.py`, which
`tools/deploy.sh` runs and fails on — that pairing is what makes silence a safe
default, and `test_the_gate_cannot_silence_production_unnoticed` guards it.
"""
from __future__ import annotations

import pathlib

import pytest

from src.utils.email_alerts import EmailAlert

REPO = pathlib.Path(__file__).resolve().parents[1]

_SMTP_ENV = {"SMTP_USER": "u", "SMTP_PASSWORD": "p", "ALERT_EMAIL": "a@b.c"}


@pytest.fixture()
def wired(monkeypatch):
    """SMTP fully configured, so a refusal can only come from the instance gate."""
    for k, v in _SMTP_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv(EmailAlert._OPT_IN, raising=False)

    reached = []
    import smtplib

    class _Probe:
        """Records the attempt instead of raising.

        The first version of this fixture raised, and both send paths catch
        `Exception` — so the raise was swallowed and every assertion inverted. A
        probe inside code that swallows must RECORD, never raise.
        """

        def __init__(self, *a, **k):
            reached.append(a)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, *a):
            pass

        def send_message(self, *a):
            pass

    monkeypatch.setattr(smtplib, "SMTP", _Probe)
    return reached


@pytest.mark.parametrize("env", ["local", "dev", "ci", "worktree", ""])
def test_no_send_path_leaves_a_non_production_instance(monkeypatch, wired, env):
    """BOTH paths. The 2026-08-24 fix touched both subjects; a gate on one only
    would leave alive exactly the path that reaches artists."""
    monkeypatch.setenv("STREAMLYTICS_ENV", env)
    a = EmailAlert()
    assert a.send_alert("panne", "<p>x</p>") is False
    assert a.send_email("artiste@example.com", "ton rapport", "<p>x</p>") is False
    assert not wired, "smtplib.SMTP was constructed off production"


def test_the_refusal_says_which_instance_and_how_to_override(monkeypatch, wired):
    monkeypatch.setenv("STREAMLYTICS_ENV", "local")
    a = EmailAlert()
    a.send_alert("panne", "<p>x</p>")
    assert "local" in a.last_error
    assert EmailAlert._OPT_IN in a.last_error, (
        "a refusal that does not name its own escape hatch is a dead end")


@pytest.mark.parametrize("opt", ["1", "true", "YES"])
def test_the_opt_in_is_explicit_and_works(monkeypatch, wired, opt):
    """Deliberately testing the mail from a dev box stays possible — per run."""
    monkeypatch.setenv("STREAMLYTICS_ENV", "local")
    monkeypatch.setenv(EmailAlert._OPT_IN, opt)
    assert EmailAlert().send_alert("panne", "<p>x</p>") is True
    assert wired, "the explicit opt-in did not let the message through"


@pytest.mark.parametrize("opt", ["", "0", "no", "maybe"])
def test_a_vague_opt_in_is_not_an_opt_in(monkeypatch, wired, opt):
    monkeypatch.setenv("STREAMLYTICS_ENV", "local")
    monkeypatch.setenv(EmailAlert._OPT_IN, opt)
    assert EmailAlert().send_alert("panne", "<p>x</p>") is False


def test_production_still_sends(monkeypatch, wired):
    """The whole point of the gate is that it changes NOTHING in production.

    Reaching `smtplib.SMTP` is the assertion: the fixture records every construction,
    so a non-empty record proves the gate let the message through.
    """
    monkeypatch.setenv("STREAMLYTICS_ENV", "production")
    assert EmailAlert().send_alert("panne réelle", "<p>x</p>") is True
    assert EmailAlert().send_email("artiste@example.com", "rapport", "<p>x</p>") is True
    assert len(wired) == 2, (
        f"production sent {len(wired)} of 2 messages — the gate is silencing prod")


def test_the_gate_cannot_silence_production_unnoticed():
    """The pairing that makes silence a safe default.

    Without `STREAMLYTICS_ENV` present in the scheduler, this gate would turn a
    missing variable into a silent production — and the silence of an alert IS the
    incident. The deploy-time parity check is what forbids that, so it is asserted
    here rather than trusted.
    """
    # The STRUCTURE, not the text. The first version of this assertion split the
    # source on a string and passed while the requirement had been deleted — the
    # comment above the dict and the dashboard entry both mention the name, so a
    # text search can never fail here. That is the exact failure this repo has
    # catalogued twice, and it landed on the one assertion protecting production
    # from silence.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_parity", REPO / "tools/check_env_parity.py")
    parity_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parity_mod)

    required = set(parity_mod._SERVICE_EXTRA.get("airflow_scheduler", ()))
    assert "STREAMLYTICS_ENV" in required, (
        "STREAMLYTICS_ENV is not required for airflow_scheduler — the container that "
        "decides the nightly mail. Losing it in prod would now mean SILENT alerts, "
        f"not merely a mislabelled subject. Required today: {sorted(required)}")

    deploy = (REPO / "tools/deploy.sh").read_text(encoding="utf-8")
    assert "check_env_parity.py" in deploy, (
        "deploy no longer runs the parity gate; the pairing is broken")
