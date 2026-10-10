"""R509 — the parser mutation run measures the tree being tested, every module, every week.

Type: Test
Uses: subprocess (a throwaway git repo), yaml
Depends on: tools/dev/mutate_parsers.py, .github/workflows/mutation-weekly.yml, .gitignore
Persists in: nothing

Measured on 2026-10-11: the first runner copied `git archive HEAD`, so after five tests
pinned SACEM survivors the rerun still reported the same 22 — the tests were written,
not committed. It now copies the working tree (tracked + untracked, not ignored).
What must hold:
1. the copy carries an untracked file and leaves an ignored one out;
2. every parser module has at least one test file that can kill its mutants;
3. the report is ignored by git (a generated report of the day, not a document);
4. the weekly workflow installs the dev extra and runs the script.

Mutation record (2026-10-11): seen red with `-co` → `ls-files` (HEAD's files only),
`--exclude-standard` dropped, the report line removed from `.gitignore`, and the
workflow's run step removed.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from tools.dev import mutate_parsers

_ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_the_copy_is_the_working_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, copy = tmp_path / "repo", tmp_path / "copy"
    repo.mkdir()
    copy.mkdir()
    _git(repo, "init", "-q")
    (repo / "committed.txt").write_text("a = 1\n")
    (repo / ".gitignore").write_text("ignored.log\n")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c")
    (repo / "tests").mkdir()
    (repo / "tests/new_test.txt").write_text("def test_x(): pass\n")
    (repo / "ignored.log").write_text("x\n")
    monkeypatch.setattr(mutate_parsers, "ROOT", repo)
    mutate_parsers._copy_worktree(copy)
    assert (copy / "committed.txt").is_file()
    assert (copy / "tests/new_test.txt").is_file(), "an uncommitted test is not measured"
    assert not (copy / "ignored.log").exists(), "an ignored file leaks into the copy"


@pytest.mark.parametrize("module", mutate_parsers.modules())
def test_every_parser_has_tests_that_can_kill_its_mutants(module: str) -> None:
    assert mutate_parsers.tests_for(module), f"no test imports src.transformers.{module}"


def test_the_report_is_not_versioned() -> None:
    rel = str(mutate_parsers.REPORT.relative_to(_ROOT))
    run = subprocess.run(["git", "check-ignore", "-q", rel], cwd=_ROOT)
    assert run.returncode == 0, f"{rel} is not ignored by git"


def test_the_weekly_workflow_runs_the_script() -> None:
    flow = yaml.safe_load((_ROOT / ".github/workflows/mutation-weekly.yml").read_text())
    runs = " ".join(s.get("run", "") for s in flow["jobs"]["mutate"]["steps"])
    assert "--extra dev" in runs, "mutmut is a dev extra: without it the run imports nothing"
    assert "tools/dev/mutate_parsers" in runs
