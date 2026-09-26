"""A push that turns `main` red mails the owner — once per breakage, not once per red push.

Type: Sub
Uses: tools/dev/ci_break_mail.py, .github/workflows/ci.yml
Depends on: nothing — fabricated `needs` and previous conclusions, nothing is sent

main was red from 2026-09-22 to 2026-09-25 and nobody read it.
"""
import importlib.util
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ci_break_mail", _ROOT / "tools/dev/ci_break_mail.py")
cbm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cbm)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Green → red mails; red → red does not; an unreadable past mails (doubt is loud)."""
    failed = cbm.failed_jobs({"gates": {"result": "success"}, "suite": {"result": "failure"}})
    assert failed == ["suite"]
    assert cbm.should_mail(failed, "success")
    assert not cbm.should_mail(failed, "failure"), "a main that STAYS red must not mail again"
    assert cbm.should_mail(failed, None), "an unknown previous run must not silence the mail"
    assert not cbm.should_mail([], "success"), "a green run never mails"


def test_ci_wires_notify_to_every_job_on_push_to_main() -> None:
    wf = yaml.safe_load((_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    jobs = wf["jobs"]
    notify = jobs["notify"]
    assert set(notify["needs"]) == set(jobs) - {"notify"}, "a job left out of `needs` breaks main in silence"
    cond = str(notify["if"])
    assert "always()" in cond and "refs/heads/main" in cond
    assert "ci_break_mail.py" in str(notify["steps"])


def test_a_cancelled_run_is_not_a_red_main() -> None:
    """2026-09-26: two runs superseded by a newer push (`cancel-in-progress`) mailed
    « main vient de passer au ROUGE — job(s) : gates, suite ». A cancelled job judged
    nothing; a cancelled previous run says nothing about whether main was red."""
    cancelled = {"gates": {"result": "cancelled"}, "suite": {"result": "cancelled"},
                 "secrets": {"result": "success"}}
    assert cbm.failed_jobs(cancelled) == []
    runs = [{"id": 3, "conclusion": None}, {"id": 2, "conclusion": "cancelled"},
            {"id": 1, "conclusion": "failure"}, {"id": 0, "conclusion": "success"}]
    assert cbm.last_verdict(runs, "3") == "failure", "the cancelled run hid a red main"
    assert cbm.last_verdict([{"id": 1, "conclusion": "cancelled"}], "9") is None
