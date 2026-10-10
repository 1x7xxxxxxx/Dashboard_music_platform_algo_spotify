"""R507 — a `pull_request_target` workflow only ever runs for Dependabot, from this repo.

Type: Utility
Uses: yaml, .github/workflows/*.yml
Triggers: pytest
Persists in: nothing

`pull_request_target` hands a write token to the PR's workflow run. Without a gate on
the actor AND on the head repository, any fork could push to our branches through it.
"""
import pathlib

import pytest
import yaml

_WORKFLOWS = sorted(pathlib.Path(".github/workflows").glob("*.yml"))
_REQUIRED = ("github.actor == 'dependabot[bot]'",
             "github.event.pull_request.head.repo.full_name == github.repository")


def ungated_jobs(workflow: dict) -> list[str]:
    """Jobs of a `pull_request_target` workflow whose `if:` lacks one of the gates."""
    triggers = workflow.get("on", workflow.get(True)) or {}
    if "pull_request_target" not in triggers:
        return []
    return [name for name, job in (workflow.get("jobs") or {}).items()
            if not all(g in str(job.get("if", "")) for g in _REQUIRED)]


@pytest.mark.parametrize("path", _WORKFLOWS, ids=[p.name for p in _WORKFLOWS])
def test_a_pull_request_target_job_is_gated_on_dependabot_and_this_repo(path):
    assert not ungated_jobs(yaml.safe_load(path.read_text())), (
        f"{path}: a pull_request_target job without the actor + head-repo gate")


def test_the_lock_workflow_exists_and_reruns_ci():
    text = pathlib.Path(".github/workflows/dependabot-lock.yml").read_text()
    assert "uv lock" in text and "gh workflow run ci.yml" in text


def test_the_detector_sees_an_ungated_job():
    bad = {"on": {"pull_request_target": {}}, "jobs": {"j": {"if": "true"}}}
    assert ungated_jobs(bad) == ["j"]
    assert ungated_jobs({"on": {"push": {}}, "jobs": {"j": {}}}) == []
