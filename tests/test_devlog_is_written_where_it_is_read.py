"""
Guard — the DEVLOG that tools write to is the DEVLOG that /resume reads.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: .claude/hooks/*.py, .claude/commands/resume.md, DEVLOG.md
Persists in: nothing (read-only assertions)

Error class: pipeline-writes-to-the-copy-nobody-reads.

`.claude/dev-docs/DEVLOG.md` is a frozen archive (last entry 2026-06-11).
`draft_devlog.py` checked it for "does today already have an entry?" and
`/devlog-promote` wrote promoted entries into it, so the whole
draft -> validate -> promote loop deposited its output where nobody looks.
Two full sessions (2026-08-21, and the night of 21->22) ended up with no DEVLOG
page at all, and the 2026-08-21 draft sat unfilled without anything noticing.

The Python side is checked on the AST, not on text: a guard that greps for a
path string passes on its own explanatory comment.
The Markdown side (a slash command, which has no AST) is checked by its
*consequence* instead of its wording — an entry promoted into the archive makes
the archive newer than the live file, which `test_the_archive_stays_behind`
catches regardless of how the command is phrased.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIVE_DEVLOG = "DEVLOG.md"
ARCHIVE_DEVLOG = REPO / ".claude" / "dev-docs" / "DEVLOG.md"

_ENTRY_DATE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})", re.MULTILINE)


_PATHLIKE = re.compile(r"^[\w./-]+\.md$")


def _is_devlog_path(value: object) -> bool:
    """A path to a DEVLOG file — not prose that merely mentions one."""
    return (
        isinstance(value, str)
        and "DEVLOG" in value
        and bool(_PATHLIKE.match(value))
    )


def _devlog_path_constants(py_file: Path) -> list[tuple[str, str]]:
    """Every DEVLOG *path* literal a tool names, read off the AST.

    Covers both `NAME = "…/DEVLOG.md"` and dict values (`{...: "DEVLOG.md"}`),
    which is how session_summary.py carries its watch list. Prose strings that
    merely mention DEVLOG.md are excluded by `_PATHLIKE` — this guard must not
    fail on a reminder message.
    """
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_devlog_path(getattr(node.value, "value", None)):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.append((target.id, node.value.value))
        elif isinstance(node, ast.Dict):
            for value in node.values:
                if isinstance(value, ast.Constant) and _is_devlog_path(value.value):
                    found.append(("<dict value>", value.value))
    return found


def _tool_python_files() -> list[Path]:
    files: list[Path] = []
    for sub in ("hooks", "scripts"):
        d = REPO / ".claude" / sub
        if d.is_dir():
            files.extend(sorted(d.glob("*.py")))
    return files


def test_every_python_tool_points_at_the_live_devlog() -> None:
    offenders = []
    for py in _tool_python_files():
        for name, value in _devlog_path_constants(py):
            if value != LIVE_DEVLOG:
                offenders.append(f"{py.relative_to(REPO)}: {name} = {value!r}")
    assert not offenders, (
        "These tools name a DEVLOG that is not the one /resume reads "
        f"({LIVE_DEVLOG!r}):\n  " + "\n  ".join(offenders)
    )


def test_the_live_devlog_is_the_one_resume_reads() -> None:
    resume = (REPO / ".claude" / "commands" / "resume.md").read_text(encoding="utf-8")
    assert "`DEVLOG.md` (repo root)" in resume, (
        "/resume no longer names the repo-root DEVLOG — this guard's premise is gone. "
        "Re-derive which file is live before editing this test."
    )


def test_the_archive_stays_behind() -> None:
    """A promotion into the archive would make it newer than the live file."""
    live_dates = _ENTRY_DATE.findall((REPO / LIVE_DEVLOG).read_text(encoding="utf-8"))
    archive_dates = _ENTRY_DATE.findall(ARCHIVE_DEVLOG.read_text(encoding="utf-8"))
    assert live_dates, "the live DEVLOG has no dated entry"
    assert archive_dates, "the archive has no dated entry"
    assert max(archive_dates) < max(live_dates), (
        f"the frozen archive ({max(archive_dates)}) is at or ahead of the live DEVLOG "
        f"({max(live_dates)}) — an entry was written to the copy nobody reads"
    )


def test_the_archive_says_it_is_an_archive() -> None:
    head = ARCHIVE_DEVLOG.read_text(encoding="utf-8").splitlines()[0]
    assert "ARCHIVE" in head, (
        f".claude/dev-docs/DEVLOG.md must announce itself as frozen; first line is {head!r}"
    )
