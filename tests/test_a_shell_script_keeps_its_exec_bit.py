"""The exec-bit checker reads the git INDEX, and sees a script stored 100644.

Type: Sub
Uses: .claude/scripts/check_exec_bit.py (non_executable_scripts), git
Depends on: git — a throwaway repository under tmp_path

Class `exec-bit-lost-outside-the-index`: on /mnt/c the disk never reports the mode back,
so only the index says whether a fresh clone will be able to run the script.
"""
import importlib.util
import subprocess
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_exec_bit", Path(__file__).resolve().parents[1] / ".claude/scripts/check_exec_bit.py")
ceb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ceb)


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    git("init", "-q")
    for name in ("lost.sh", "kept.sh"):
        (tmp_path / name).write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
    git("add", "lost.sh", "kept.sh")
    git("update-index", "--chmod=-x", "lost.sh")
    git("update-index", "--chmod=+x", "kept.sh")
    assert ceb.non_executable_scripts(tmp_path) == ["lost.sh"]
