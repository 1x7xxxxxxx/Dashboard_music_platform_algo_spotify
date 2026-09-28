"""R305 — one archive, every file of it indexed, and nothing alive still points at an old path.

Type: Test
Uses: git ls-files, archive/README.md
Depends on: archive/ (the consolidated archive since 2026-09-28)
Persists in: nothing

The owner asked (2026-09-28) for ONE archive folder instead of three (`.claude/.retired/`,
`.claude/dev-docs/archives/`, `archive/`), and for documentation read on demand rather than kept
current. Two ways that goes wrong, silently:
- a file lands in `archive/` with no line in the index — nobody can tell why it is there, or
  where it came from to bring it back;
- a live file keeps naming the OLD path — a runbook, a hook message or a test that sends the
  reader to a file that is no longer there. The move repointed 18 live files; this keeps the
  count at zero. History (DEVLOG, the roadmap archive, `.test_durations`) is exempt: it cites a
  file because it once existed.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "archive" / "README.md"
HISTORY = {"DEVLOG.md", ".claude/dev-docs/DEVLOG.md", ".claude/dev-docs/roadmap/archive.md",
           ".test_durations", "archive/README.md"}
#: This file quotes the defects it catches (a moved path in a comment) — it is not a pointer.
_SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()
_ROW = re.compile(r"^\| `([^`]+)` \| `([^`]+)` \|", re.M)


def index_rows(text: str) -> dict[str, str]:
    """{archived path: old path} from the index table. Pure."""
    return dict(_ROW.findall(text))


def unindexed(archived: list[str], rows: dict[str, str]) -> list[str]:
    return sorted(f for f in archived if f != "archive/README.md" and f not in rows)


def stale_pointers(rows: dict[str, str], texts: dict[str, str]) -> list[str]:
    """`live file → old path` for every live file still naming an archived file's old path."""
    # A WHOLE path, never a suffix of a longer one: `scripts/backup_db.sh` is also the tail of
    # its own new home `archive/scripts/scripts/backup_db.sh` — matched as a substring, every
    # correctly repointed line read as stale (2026-09-28, R306).
    olds = sorted(set(rows.values()), key=len, reverse=True)
    if not olds:
        return []
    # ONE alternation, longest first: 90 patterns × 1 700 files took 29 s one by one.
    pat = re.compile(r"(?<![\w/.-])(" + "|".join(map(re.escape, olds)) + r")")
    out = set()
    for f, text in texts.items():
        if f in HISTORY or f.startswith("archive/") or f == _SELF:
            continue
        out |= {f"{f} → {m}" for m in pat.findall(text)}
    return sorted(out)


def _tracked() -> list[str]:
    return subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                          text=True).stdout.split()


def test_every_archived_file_has_its_line_and_every_line_its_file() -> None:
    rows = index_rows(INDEX.read_text(encoding="utf-8"))
    archived = [f for f in _tracked() if f.startswith("archive/")]
    missing = unindexed(archived, rows)
    assert not missing, f"archived without a line in archive/README.md: {missing}"
    ghosts = sorted(p for p in rows if not (ROOT / p).exists())
    assert not ghosts, f"indexed but absent from archive/: {ghosts}"


def test_no_live_file_points_at_an_archived_files_old_path() -> None:
    rows = index_rows(INDEX.read_text(encoding="utf-8"))
    texts = {}
    for f in _tracked():
        p = ROOT / f
        # Every text a reader can be sent from — prose AND code: the pointer is a path string.
        if p.suffix.lstrip(".") in {"md", "py", "sh", "yml", "yaml", "json", "js", "toml"} \
                or f == "Makefile":
            try:
                texts[f] = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
    stale = stale_pointers(rows, texts)
    assert not stale, ("live files still send the reader to a path that moved to archive/ — "
                       "repoint them:\n  " + "\n  ".join(stale))


def test_the_detectors_see_what_they_are_written_for_not_vacuous() -> None:
    index = "| `archive/docs/a.md` | `.claude/dev-docs/a.md` | figé | 2026-09-28 |\n"
    rows = index_rows(index)
    assert rows == {"archive/docs/a.md": ".claude/dev-docs/a.md"}
    assert unindexed(["archive/docs/a.md", "archive/docs/b.md", "archive/README.md"], rows) \
        == ["archive/docs/b.md"]
    texts = {"CLAUDE.md": "see .claude/dev-docs/a.md", "DEVLOG.md": ".claude/dev-docs/a.md",
             "archive/docs/x.md": ".claude/dev-docs/a.md", "tools/y.sh": "nothing"}
    assert stale_pointers(rows, texts) == ["CLAUDE.md → .claude/dev-docs/a.md"]
    nested = {"archive/scripts/scripts/b.sh": "scripts/b.sh"}
    assert stale_pointers(nested, {"x.md": "see `archive/scripts/scripts/b.sh`"}) == [], \
        "the new path contains the old one as a suffix — not a stale pointer"
    assert stale_pointers(nested, {"x.md": "run `scripts/b.sh`"}) == ["x.md → scripts/b.sh"]
