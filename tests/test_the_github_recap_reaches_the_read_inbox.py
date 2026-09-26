"""The GitHub-side nightly recap says what it sees — and it is scheduled, every night.

Type: Sub
Uses: tools/dev/github_nightly_recap.py (build, probe_prod), .github/workflows/nightly-recap.yml
Depends on: nothing (no network: the opener is injected)
Persists in: nothing

R181 (2026-09-26). The production recap goes to an inbox nobody reads; this one travels
the road that reaches the read inbox. Three properties: an unreachable production is RED
(never « unknown », never green), a calm night still produces a mail, and the workflow is
scheduled and sends to the address the other GitHub mails use.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "github_nightly_recap", _ROOT / "tools" / "dev" / "github_nightly_recap.py")
recap = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = recap
_spec.loader.exec_module(recap)

_NOW = datetime(2026, 9, 27, 6, 47, tzinfo=timezone.utc)
_GREEN = {"CI main": {"state": "green", "since": None, "url": None}}


class _Resp:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _raises(*a, **k):
    raise OSError("connection refused")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """An unreachable or failing production is red; a 200 is green."""
    assert recap.probe_prod("http://x/health", opener=_raises)["state"] == "red"
    assert recap.probe_prod("http://x/health", opener=lambda *a, **k: _Resp(503))["state"] == "red"
    assert recap.probe_prod("http://x/health", opener=lambda *a, **k: _Resp(200))["state"] == "green"


def test_a_calm_night_still_makes_a_mail_and_a_red_one_says_so() -> None:
    subject, body, red = recap.build(_GREEN, {"state": "green", "detail": "HTTP 200"}, _NOW)
    assert not red and "nuit calme" in subject and "Production" in body
    subject, body, red = recap.build(_GREEN, {"state": "red", "detail": "HTTP 503"}, _NOW)
    assert red and "attention" in subject and "HTTP 503" in body
    unreadable = {"CI main": {"state": "unreadable", "since": None, "url": None}}
    _, body, _ = recap.build(unreadable, {"state": "green", "detail": "HTTP 200"}, _NOW)
    assert "✅ <b>CI main" not in body


def test_the_workflow_runs_every_night_and_mails_the_read_inbox() -> None:
    wf = yaml.safe_load((_ROOT / ".github" / "workflows" / "nightly-recap.yml").read_text(
        encoding="utf-8"))
    triggers = wf.get("on") or wf.get(True)
    assert any(c["cron"].split()[2:] == ["*", "*", "*"] for c in triggers["schedule"])
    step = next(s for s in wf["jobs"]["recap"]["steps"]
                if "github_nightly_recap.py" in s.get("run", ""))
    assert "PROD_HEALTH_MAIL_TO" in step["env"], "the address the CI break mails reach"
