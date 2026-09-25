"""A red `prod-health.yml` run mails the owner — it does not rely on GitHub notifications.

Type: Sub
Uses: yaml, tools/dev/mail_red_verdict.py, .github/workflows/prod-health.yml
Depends on: nothing — parses the workflow and builds the mail, sends nothing

On 2026-09-24 production was down from 11:45 to 20:51 UTC. `prod-health.yml` was red at
11:45; its verdict went to GitHub notifications on an address nobody reads, and the
outage was found that evening by a failed deploy (R166). The run now ends with a step
that mails the owner on failure, from outside the server that was down.
"""
import importlib.util
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _ROOT / ".github/workflows/prod-health.yml"
_TOOL = _ROOT / "tools/dev/mail_red_verdict.py"

_spec = importlib.util.spec_from_file_location("mail_red_verdict", _TOOL)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _mail_steps_that_follow_the_probe(workflow: dict) -> list[str]:
    """Names of `if: failure()` steps, after the probe, that run the mailer with its env."""
    steps = next(iter(workflow["jobs"].values()))["steps"]
    probe = next((i for i, s in enumerate(steps) if "test_prod_health.py" in s.get("run", "")),
                 None)
    if probe is None:
        return []
    return [s["name"] for s in steps[probe + 1:]
            if "failure()" in str(s.get("if", ""))
            and "mail_red_verdict.py" in s.get("run", "")
            and set(_mod._REQUIRED) <= set(s.get("env") or {})]


def test_the_prod_check_mails_its_red_verdict() -> None:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert _mail_steps_that_follow_the_probe(workflow), (
        "prod-health.yml has no `if: failure()` step running tools/dev/mail_red_verdict.py "
        f"with {_mod._REQUIRED} after the probe: a red run reaches nobody (R166).")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The workflow as it was on 2026-09-24 — probe only, no mail — must be refused."""
    before = {"jobs": {"prod-health": {"steps": [
        {"uses": "actions/checkout@v6"},
        {"name": "Probe", "run": "pytest tests/test_prod_health.py -v"},
    ]}}}
    assert _mail_steps_that_follow_the_probe(before) == []
    # A mail step that runs only on success, or lacks its credentials, is the same hole.
    before["jobs"]["prod-health"]["steps"].append(
        {"name": "Mail", "run": "python tools/dev/mail_red_verdict.py",
         "env": {k: "x" for k in _mod._REQUIRED}})
    assert _mail_steps_that_follow_the_probe(before) == []


def test_missing_configuration_refuses_loudly(monkeypatch, capsys) -> None:
    for k in _mod._REQUIRED:
        monkeypatch.delenv(k, raising=False)
    assert _mod.main() == 1
    assert "PROD_HEALTH_MAIL_TO" in capsys.readouterr().out


def test_the_mail_points_at_the_run(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_FROM", "alerts@example.org")
    msg = _mod.build_message({
        "SMTP_FROM": "alerts@example.org", "PROD_HEALTH_MAIL_TO": "owner@example.org",
        "GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "42",
        "GITHUB_WORKFLOW": "Prod — Daily health check"})
    assert msg["To"] == "owner@example.org"
    assert "alerts@example.org" in msg["From"]
    assert "https://github.com/o/r/actions/runs/42" in msg.get_content()
