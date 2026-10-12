"""A CI job that runs `uv sync` and then a bare `python3` must put the venv on PATH.

Type: Hook
Uses: .github/workflows/*.yml (read only)
Triggers: R523 — the nightly `error-class-audit` went red on 2026-10-11 because
three signatures called `python3 -c "import pytest…"`. On the runner, bare
`python3` is the SYSTEM interpreter: `uv sync` filled `.venv/` and nothing ever
used it. Before R495 the resulting ModuleNotFoundError counted as a HIT; after,
it is (correctly) no verdict, exit 2.
Depends on: pyyaml
Persists in: nothing
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
# `uv sync` as a COMMAND of the step: a `#` comment line naming it does not count.
_SYNC = re.compile(r"^(?!\s*#).*\buv sync\b", re.MULTILINE)
_VENV_ON_PATH = re.compile(r"\.venv/bin\"?\s*>>\s*\"?\$GITHUB_PATH")


def syncs_that_leave_the_venv_off_path(workflow_dir: Path = WORKFLOWS) -> list[str]:
    """Return `file:job:step` for each `uv sync` step that does not put `.venv/bin` on PATH.

    Checked on the sync step itself rather than on the later `python3` calls: whether a
    bare `python3` needs a third-party module is not readable from the YAML (most of the
    `python3 -c` lines are stdlib), so the guard enforces the shape that makes every
    later call safe.
    """
    offenders: list[str] = []
    for wf in sorted(workflow_dir.glob("*.yml")):
        doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        for job_name, job in (doc.get("jobs") or {}).items():
            for i, step in enumerate(job.get("steps") or []):
                run = step.get("run") or ""
                if _SYNC.search(run) and not _VENV_ON_PATH.search(run):
                    offenders.append(f"{wf.name}:{job_name}:{step.get('name') or i}")
    return offenders


def test_every_uv_sync_puts_the_venv_on_path() -> None:
    assert syncs_that_leave_the_venv_off_path() == [], (
        "These steps run `uv sync` without `echo \"$PWD/.venv/bin\" >> \"$GITHUB_PATH\"`: "
        "every later bare `python3` in the job gets the runner's system interpreter, "
        "which has none of the project's dependencies."
    )


def test_the_guard_goes_red_on_the_defect_it_was_written_for(tmp_path: Path) -> None:
    (tmp_path / "x.yml").write_text(
        "jobs:\n  audit:\n    steps:\n"
        "      - run: uv sync --frozen\n"
        "      - run: python3 .claude/scripts/audit_runner.py --all\n",
        encoding="utf-8",
    )
    assert syncs_that_leave_the_venv_off_path(tmp_path) == ["x.yml:audit:0"]
    (tmp_path / "x.yml").write_text(
        "jobs:\n  audit:\n    steps:\n"
        "      - run: uv sync --frozen && echo \"$PWD/.venv/bin\" >> \"$GITHUB_PATH\"\n"
        "      - run: python3 .claude/scripts/audit_runner.py --all\n",
        encoding="utf-8",
    )
    assert syncs_that_leave_the_venv_off_path(tmp_path) == []
