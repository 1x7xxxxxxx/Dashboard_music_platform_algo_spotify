"""Fixtures partagées pour tous les tests."""
import io
import sys
import os
import pytest
import pandas as pd

# Rendre src/ importable sans installation du package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers CSV en mémoire (pas de fichiers temporaires nécessaires)
# ---------------------------------------------------------------------------

def make_csv_bytes(content: str, encoding: str = "utf-8") -> bytes:
    return content.encode(encoding)


def make_tmp_csv(tmp_path, filename: str, content: str, encoding: str = "utf-8"):
    """Crée un fichier CSV temporaire et retourne son Path."""
    p = tmp_path / filename
    p.write_bytes(content.encode(encoding))
    return p


@pytest.fixture
def tmp_csv(tmp_path):
    """Factory fixture : make_tmp_csv(filename, content)."""
    def _factory(filename: str, content: str, encoding: str = "utf-8"):
        return make_tmp_csv(tmp_path, filename, content, encoding)
    return _factory


# ---------------------------------------------------------------------------
# The silence that let four waves of tenant-isolation work ship unverified
# ---------------------------------------------------------------------------
#
# ~160 tests carry `pytestmark = requires_live_db()`. Without Postgres on 5433
# they skip, pytest prints "N passed, 163 skipped", and the run reads as green.
#
# Measured 2026-08-22: four waves of credential and tenant-isolation fixes were
# written, guarded and COMMITTED against that green. Starting the database turned
# "1065 passed" into "1217 passed, 1 FAILED" — and the failure was in the Instagram
# uniqueness protection that had just been presented as closed.
#
# The suite is not required to have a database. It IS required to say, loudly, that
# the guards which need one did not run — because "163 skipped" scrolls past and
# "green" does not.

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    from tests.db_gate import DB_HOST, DB_PORT, db_ready

    if db_ready():
        return
    skipped = terminalreporter.stats.get("skipped", [])
    gated = sum(1 for r in skipped
                if "needs the live schema" in " ".join(str(x) for x in r.longrepr or ()))
    if not gated:
        return
    tw = terminalreporter
    tw.write_sep("=", "GARDES NON EXÉCUTÉS", red=True, bold=True)
    tw.write_line(
        f"{gated} test(s) exigeant une base ont été SAUTÉS — dont l'isolation "
        f"locataire, l'unicité d'identité et le parcours d'onboarding."
    )
    tw.write_line(
        "Cette exécution ne prouve RIEN sur ces sujets. Pour les lancer :"
    )
    tw.write_line(
        f"    docker start postgres_spotify_airflow   # puis relancer  "
        f"(attendu sur {DB_HOST}:{DB_PORT})"
    )


# ---------------------------------------------------------------------------
# The suite sent real email to real people
# ---------------------------------------------------------------------------
#
# Measured 2026-08-23. `test_admin_hypeddit_buttons.py::test_every_button_survives_a_click[admin]`
# presses every button on the admin view. One of them is `📧 Renvoyer vérification`
# (`admin.py:685`), which calls `send_verification_email(sel_user['email'], …)` — an
# address read from whatever database the run points at. Locally that is the migrated
# copy of production, so the recipient is a real beta tester, and `.env` holds real
# Gmail SMTP credentials. Three suite runs on 2026-08-23 delivered three verification
# emails, each carrying `http://localhost:8501?page=verify&token=…` because no local
# process sets APP_BASE_URL.
#
# Nothing prevented it: there was no network or SMTP boundary in this file at all.
#
# Why RECORD-then-fail rather than just raise: `send_verification_email` wraps its send
# in `except Exception`, so an exception alone is swallowed, the button reports a
# failure, and the test stays green — the send would be blocked but no one would ever
# learn the test attempts it. The attempt is recorded and asserted at teardown, where
# the application's error handling cannot reach it.
#
# A test that legitimately exercises the send path patches `smtplib.SMTP` itself; its
# patch lands after this one, so it is never recorded and never fails here.

@pytest.fixture(autouse=True)
def _no_real_smtp(monkeypatch, request):
    """No test may open a real SMTP connection. Records attempts, fails at teardown."""
    import smtplib

    attempts: list[str] = []

    def _blocked(*args, **kwargs):
        host = kwargs.get("host", args[0] if args else "")
        port = kwargs.get("port", args[1] if len(args) > 1 else "")
        attempts.append(f"{host}:{port}")
        raise ConnectionRefusedError(
            "blocked by tests/conftest.py::_no_real_smtp — a test must not send email"
        )

    monkeypatch.setattr(smtplib, "SMTP", _blocked)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _blocked)
    # Exposed so the meta-test that deliberately trips this boundary can consume its
    # own attempt. Nothing else should touch it.
    request.node._smtp_attempts = attempts

    yield

    assert not attempts, (
        f"{request.node.nodeid} opened a REAL SMTP connection to {', '.join(attempts)}.\n"
        f"The credentials come from .env and the recipient from the database the run "
        f"points at — locally, a copy of production, so this delivers mail to real "
        f"people with a link to http://localhost:8501.\n"
        f"Patch the send in the test — `monkeypatch.setattr(<module>, "
        f"'send_verification_email', lambda *a, **k: True)` — or mock `smtplib.SMTP` "
        f"yourself if the send path is what you mean to exercise."
    )
