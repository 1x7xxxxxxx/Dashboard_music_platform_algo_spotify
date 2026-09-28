"""R305 — the on-demand inventory decides keep/archive by the PATH a live file cites.

Type: Test
Uses: tools/dev/repo_inventory.py (readers_of, decide_doc, decide_script)
Persists in: nothing

Code-critic (2026-09-28): six documents that LOOKED frozen were still read — by a runbook, an
ADR, CLAUDE.md, a view's comment. A title is not a reader. And the first run declared the six
`architecture_dossier/part*.py` dead: `main.py` imports them by MODULE name, not by path.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev"))

import repo_inventory as ri  # noqa: E402


def test_a_module_imported_by_name_by_a_sibling_has_a_reader() -> None:
    texts = {"tools/dev/d/main.py": "from part1 import PART1\n", "x.md": ""}
    assert ri.readers_of("tools/dev/d/part1.py", texts) == ["tools/dev/d/main.py"]
    assert ri.readers_of("tools/dev/other/part1.py", texts) == [], "import from another folder"


def test_history_is_not_a_reader() -> None:
    texts = {"DEVLOG.md": "see a/b.md", ".test_durations": "a/b.md", "live.md": ""}
    assert ri.readers_of("a/b.md", texts) == []


def test_a_command_an_adr_or_code_keeps_a_document_prose_alone_does_not_when_frozen() -> None:
    assert ri.decide_doc("d/x.md", [".claude/commands/resume.md"], age_days=90)[0] == "garder"
    assert ri.decide_doc("d/x.md", ["docs/adr/ADR-006-x.md"], age_days=90)[0] == "garder"
    assert ri.decide_doc("d/x.md", ["src/a.py"], age_days=90)[0] == "garder"
    assert ri.decide_doc("d/x.md", ["d/runbook.md"], age_days=90)[0] == "archiver"
    assert ri.decide_doc("d/x.md", ["d/runbook.md"], age_days=3)[0] == "garder"
    assert ri.decide_doc("d/x.md", [], age_days=0)[0] == "archiver"


def test_a_script_named_only_in_prose_is_archived_a_run_one_is_kept() -> None:
    assert ri.decide_script("tools/a.py", ["Makefile"], False)[0] == "garder"
    assert ri.decide_script("tools/a.py", ["docs/x.md"], False)[0] == "archiver"
    assert ri.decide_script("tools/a.py", ["Makefile"], True)[0] == "archiver"
