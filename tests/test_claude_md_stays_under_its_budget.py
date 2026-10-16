"""CLAUDE.md stays under its line budget, and every `§n` it cites exists (R631).

Type: Hook
Uses: CLAUDE.md, .claude/dev-docs/claude-md-measures.md
Persists in: nothing

Measured 2026-10-16: CLAUDE.md had grown to 688 lines, most of them dated measurements
written as the evidence of a rule. The baseline fleet audit (`audit_fleet.py`) charges a
CLAUDE.md over 400 lines, and every line is paid in context on every turn. R631 MOVED the
measurements verbatim to `claude-md-measures.md` and left a `§n` pointer in their place.

guard_scope: the line count of CLAUDE.md, and a `§n` / `§nbis` pointer in CLAUDE.md that
names no `## §n` heading of the measures doc. NOT covered: a pointer to a section that
exists but no longer says what the rule claims; a measurement re-added inside the budget.

Mutation record (2026-10-16): seen red on CLAUDE.md + 10 lines (404 ≥ 400) and on the
`## §2bis` heading renamed `## §2b` (dangling pointer); green once both were restored.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MD = ROOT / "CLAUDE.md"
MEASURES = ROOT / ".claude" / "dev-docs" / "claude-md-measures.md"
BUDGET = 400
_POINTER = re.compile(r"§(\d+(?:bis|ter)?)\b")
_HEADING = re.compile(r"^## §(\d+(?:bis|ter)?) ", re.M)


def _dangling(claude_md: str, measures: str) -> set[str]:
    return set(_POINTER.findall(claude_md)) - set(_HEADING.findall(measures))


def test_claude_md_is_under_its_budget() -> None:
    n = len(CLAUDE_MD.read_text(encoding="utf-8").splitlines())
    assert n < BUDGET, (f"CLAUDE.md has {n} lines (budget {BUDGET}) — move dated measurements "
                        f"to {MEASURES.relative_to(ROOT)} and leave a §n pointer")


def test_every_section_pointer_resolves() -> None:
    missing = _dangling(CLAUDE_MD.read_text(encoding="utf-8"),
                        MEASURES.read_text(encoding="utf-8"))
    assert not missing, f"CLAUDE.md cites sections absent from claude-md-measures.md: {missing}"


def test_the_detector_tells_a_bis_from_its_parent() -> None:
    assert _dangling("voir §2bis", "## §2 — x\n") == {"2bis"}
    assert _dangling("voir §2 et §2bis", "## §2 — x\n## §2bis — y\n") == set()
    assert _dangling("§3", "texte ## §3 — pas en tête de ligne\n") == {"3"}


def test_the_pointer_scan_is_not_vacuous() -> None:
    """Zero dangling pointers means nothing if the scan found zero pointers."""
    pointers = set(_POINTER.findall(CLAUDE_MD.read_text(encoding="utf-8")))
    headings = set(_HEADING.findall(MEASURES.read_text(encoding="utf-8")))
    assert len(pointers) >= 10 and len(headings) >= 10, (pointers, headings)
