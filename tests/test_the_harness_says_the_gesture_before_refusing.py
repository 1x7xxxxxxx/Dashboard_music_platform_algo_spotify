"""R463 — two refusals of the night are said BEFORE they happen, or with the gesture.

Type: Test
Uses: tools/dev/require_roadmap_id.py (verdict), Makefile (test-changed)
Depends on: nothing — pure functions and the Makefile text

`night-status` counted 41 refusals of the durations hook in 7 days: `make test-changed`
had already measured the new tests, the file was simply never staged. And on 2026-10-07 a
« Roadmap : » commit widening R461's scope carried the files a refused commit had left in
the index; the refusal named the scope, not the index.

Mutation record (2026-10-07): the `git diff --quiet -- .test_durations` line removed →
red; `CHECKLIST not in files` → `False` (hint on every stray) → red.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("_r463_roadmap", ROOT / "tools/dev/require_roadmap_id.py")
rid = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rid)

PARENT = ("## 📋 Tâches ouvertes\n\n| id | Tâche | P | Mesuré par |\n|---|---|---|---|\n"
          "| R9 | x <!-- critic: non — t --> <!-- scope: src/dashboard/views/a.py --> | P3 | t |\n")


def test_a_roadmap_commit_carrying_stray_code_names_the_files_to_unstage():
    files = [rid.CHECKLIST, "src/dashboard/views/b.py"]
    reason = rid.verdict(files, "Roadmap : R9 — périmètre élargi", PARENT)
    assert reason and "git reset src/dashboard/views/b.py" in reason


def test_a_code_commit_out_of_scope_keeps_the_plain_reason():
    reason = rid.verdict(["src/dashboard/views/b.py"], "R9 : y", PARENT)
    assert reason and "hors du périmètre" in reason and "git reset" not in reason
