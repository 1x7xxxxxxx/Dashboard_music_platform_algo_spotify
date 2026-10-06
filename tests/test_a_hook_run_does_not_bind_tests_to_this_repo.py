"""Guard: a test suite run from a git hook never writes into this repo's index.

Type: Sub
Uses: tests/conftest.py (GIT_BINDING_VARS), subprocess (a throwaway git repo)
Triggers: pytest
Persists in: nothing

Measured 2026-10-06. The pre-commit hook `governance-readers` runs pytest with the
GIT_INDEX_FILE git exported for the commit; `tests/test_code_without_a_trace_is_flagged.py`
ran `git add` in a tmp repo and that landed in THIS repo's index (`fatal: unable to read
<sha>` afterwards). The guard runs a child pytest with a sacrificial index in its
environment and checks that the sacrificial index is never written.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_CHILD = '''
import subprocess

def test_git_add_in_a_tmp_repo(tmp_path):
    for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    (tmp_path / "f.txt").write_text("x\\n")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path, check=True)
'''


def test_a_hook_exported_index_is_not_written(tmp_path: Path) -> None:
    sacrificial = tmp_path / "outer-index"
    child = tmp_path / "child" / "test_child.py"
    child.parent.mkdir()
    child.write_text(_CHILD, encoding="utf-8")
    env = {**os.environ, "GIT_INDEX_FILE": str(sacrificial),
           "PYTHONPATH": os.pathsep.join(filter(None, [str(REPO), os.environ.get("PYTHONPATH")]))}
    # The repo's conftest is loaded as a plugin: the probe stays out of the real tree.
    run = subprocess.run(
        [sys.executable, "-m", "pytest", str(child), "-q", "-p", "tests.conftest",
         "-p", "no:randomly", "-p", "no:cacheprovider", "-n", "0",
         f"--rootdir={child.parent}", f"--basetemp={tmp_path / 'bt'}"],
        cwd=child.parent, env=env, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    assert not sacrificial.exists(), (
        "a test's `git add` in its own tmp repo wrote the index the parent git exported — "
        "tests/conftest.py must drop GIT_BINDING_VARS")
