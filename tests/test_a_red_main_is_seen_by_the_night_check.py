"""`make night-check` says when main's CI is red.

Type: Sub
Uses: tools/dev/night_run.py (`red_main`)
Depends on: nothing — the `gh` rows are fabricated
Persists in: nothing

On 2026-09-26 main stayed red for a whole night — more than 60 runs — while every unit
of work passed `make test-changed` and `night-check` returned 0. The check now reads
the CI verdict; this file proves the reading.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "night_run_ci", Path(__file__).resolve().parents[1] / "tools/dev/night_run.py")
night_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(night_run)


def _run(at: str, conclusion: str, status: str = "completed") -> dict:
    return {"createdAt": at, "conclusion": conclusion, "status": status,
            "displayTitle": f"commit {at}"}


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: three failures in a row — one cancelled run between them — are a
    streak of three, named by the newest, and a push still running on top does not
    clear it; a green newest verdict, and a run in progress on top of it, say nothing."""
    night = [_run("2026-09-26T03:23", "failure"), _run("2026-09-26T03:26", "failure"),
             _run("2026-09-26T03:29", "cancelled"), _run("2026-09-26T03:31", "failure"),
             _run("2026-09-25T22:00", "success")]
    said = night_run.red_main(night)
    assert said is not None and "3 exécution(s)" in said and "03:31" in said
    # A push in progress does not clear a red main: the newest VERDICT still decides.
    pending = night + [_run("2026-09-26T03:34", "", status="in_progress")]
    assert night_run.red_main(pending) is not None
    green = night + [_run("2026-09-26T06:40", "success")]
    assert night_run.red_main(green) is None
    running = green + [_run("2026-09-26T06:45", "", status="in_progress")]
    assert night_run.red_main(running) is None


def test_a_stale_mail_journal_is_seen() -> None:
    """The owner does not read the automated mails; the journal's age is what tells a
    session to go read them. Newest row wins; no row at all is unknown, not fresh."""
    text = ("| received | subject |\n|---|---|\n"
            "| 2026-09-21 08:00 | a |\n| 2026-09-25 14:46 | b |\n")
    assert night_run.mail_journal_age_days(text, "2026-09-26") == 1
    assert night_run.mail_journal_age_days(text, "2026-09-25") == 0
    assert night_run.mail_journal_age_days("| received |\n|---|\n", "2026-09-26") is None
