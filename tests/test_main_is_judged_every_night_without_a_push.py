"""R448 → R650 — main was judged every night; since R650 only prod-health keeps a cron.

Type: Sub
Uses: .github/workflows/ci.yml, tools/dev/ci_break_mail.py
Depends on: nothing — the workflow is parsed, nothing is sent

A date, a dependency or an API can break main with no commit at all; until R448 the red
waited for the next unrelated push and was blamed on it.
"""
import importlib.util
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]

def _wf() -> dict:
    return yaml.safe_load((_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))


_spec = importlib.util.spec_from_file_location("ci_break_mail_r448", _ROOT / "tools/dev/ci_break_mail.py")
cbm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cbm)


def test_only_prod_health_keeps_a_schedule() -> None:
    """R650 (2026-10-26, owner decision): no cron but the production health check — CI, the
    recap, the security audit and the mutation run follow main's pushes instead."""
    scheduled = set()
    for wf in (_ROOT / ".github/workflows").glob("*.y*ml"):
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        triggers = doc.get("on", doc.get(True)) or {}
        if isinstance(triggers, dict) and triggers.get("schedule"):
            scheduled.add(wf.name)
    assert scheduled == {"prod-health.yml"}


def test_ci_runs_on_main_pushes_and_by_hand() -> None:
    wf = _wf()
    triggers = wf.get("on", wf.get(True))
    assert "main" in triggers["push"]["branches"] and "workflow_dispatch" in triggers


def test_a_red_main_mails_and_the_commit_judge_runs_on_every_event() -> None:
    jobs = _wf()["jobs"]
    assert "'push'" in str(jobs["notify"]["if"]) and "'schedule'" not in str(jobs["notify"]["if"])
    assert "if" not in jobs["roadmap"], "every remaining event carries a range to judge"


def test_the_heavy_audits_run_only_when_what_they_audit_changes() -> None:
    for name, must in (("security-nightly.yml", "uv.lock"),
                       ("mutation-weekly.yml", "src/transformers/**")):
        doc = yaml.safe_load((_ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
        triggers = doc.get("on", doc.get(True))
        assert must in triggers["push"]["paths"], name
        assert doc["concurrency"]["cancel-in-progress"] is True, name


def test_the_previous_verdict_counts_nightly_runs(monkeypatch) -> None:
    """Green→red is judged against the last main run, scheduled or pushed."""
    seen = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"workflow_runs": []}'

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        return _Resp()

    monkeypatch.setattr(cbm.urllib.request, "urlopen", fake_urlopen)
    cbm.previous_conclusion({"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t", "GITHUB_RUN_ID": "1"})
    assert "branch=main" in seen["url"] and "event=" not in seen["url"]
