"""R448 — main is judged every night, so drift without a push still turns it red.

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


def test_ci_runs_on_a_nightly_schedule() -> None:
    wf = _wf()
    triggers = wf.get("on", wf.get(True))          # PyYAML reads the bare key `on` as True
    crons = [c["cron"] for c in triggers.get("schedule") or []]
    assert len(crons) == 1 and len(crons[0].split()) == 5 and crons[0].split()[2:] == ["*", "*", "*"]


def test_a_nightly_red_mails_and_the_commit_judge_stays_out() -> None:
    jobs = _wf()["jobs"]
    assert "'schedule'" in str(jobs["notify"]["if"]) and "'push'" in str(jobs["notify"]["if"])
    # a schedule has no pushed range: judging HEAD~1 would re-judge yesterday's commit
    assert str(jobs["roadmap"]["if"]).replace(" ", "") == "${{github.event_name!='schedule'}}"


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
