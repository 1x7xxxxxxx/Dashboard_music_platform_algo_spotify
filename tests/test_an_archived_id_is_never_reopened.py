"""R564 — an id that already heads an archive entry cannot be reopened in the index.

Type: Test
Uses: tools/dev/require_roadmap_id.py (reopened, the commit-msg gate's helper)
Depends on: the two roadmap files, and the 2026-10-14 state replayed from git (81b20974)
Persists in: nothing

R562 was given on 2026-10-13 (debt-trend, archived) and again on 2026-10-14 (harness
pass). `make roadmap-close ID=R562` then retired the row and wrote no archive entry —
a second close of an id is refused — and nothing said so.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))
import require_roadmap_id as gate  # noqa: E402

_INDEX = (f"{gate.INDEX_TITLE}\n\n| id | Tâche | P | Mesuré par |\n|---|---|---|---|\n"
          "| R562 | passe harnais | P4 | x |\n| R563 | autre | P4 | y |\n")
_ARCHIVE = "# Roadmap — archive\n\n## ✅ R562 — debt-trend (livrée 2026-10-13)\n\n- [x] **R562**\n"


def test_an_open_id_already_archived_is_reported() -> None:
    assert gate.reopened(_INDEX, _ARCHIVE) == {"R562"}


def test_an_id_merely_cited_in_the_archive_is_not_a_collision() -> None:
    cited_only = "## ✅ R100 — x\n\n  voir R562 et R563 plus tard\n"
    assert gate.reopened(_INDEX, cited_only) == set()


def test_the_2026_10_14_state_is_caught() -> None:
    show = lambda p: subprocess.run(["git", "show", f"81b20974:{p}"], cwd=ROOT,  # noqa: E731
                                    capture_output=True, text=True).stdout
    checklist, archive = show(gate.CHECKLIST), show(gate.ARCHIVE)
    if not checklist:  # shallow clone without that commit
        return
    assert "R562" in gate.reopened(checklist, archive)


def test_the_live_roadmap_reopens_nothing() -> None:
    checklist = (ROOT / gate.CHECKLIST).read_text(encoding="utf-8")
    archive = (ROOT / gate.ARCHIVE).read_text(encoding="utf-8")
    assert gate.reopened(checklist, archive) == set()
