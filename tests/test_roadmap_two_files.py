"""Non-regression floor for the two-file roadmap.

Installed 2026-08-03, when the single 891-line `checklist.md` was split into an
active file (19 open items) and an archive (214 delivered ones). Every number
below was TRUE at the split.

The failure this guards against is specific and was named before it happened: a
rotation that **shrinks the denominator** improves the completion percentage
without delivering anything. Moving an item from active to archive must leave the
total untouched; deleting one must not be silently indistinguishable from
finishing one.

Raise a floor when the real number rises. Never lower one to make a test pass —
lowering it is the regression this file exists to catch.
"""
from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    """Walk up to the directory that owns .claude/ — never a fixed parents[N]."""
    for d in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test — is it installed in the right repo?")


REPO = _repo_root()
ROADMAP = REPO / ".claude" / "dev-docs" / "roadmap"
ACTIVE = ROADMAP / "checklist.md"
ARCHIVE = ROADMAP / "archive.md"

_OPEN = re.compile(r"^\s*- \[ \]", re.M)
_DONE = re.compile(r"^\s*- \[[xX]\]", re.M)

# Measured at the 2026-08-03 split: 19 open + 221 done = 240 items total,
# of which 214 delivered ones landed in the archive.
_TOTAL_ITEMS_FLOOR = 240
_ARCHIVE_DONE_FLOOR = 214


def _counts(p: Path) -> tuple[int, int]:
    t = p.read_text(encoding="utf-8")
    return len(_OPEN.findall(t)), len(_DONE.findall(t))


def test_both_roadmap_files_exist():
    """Rule 17 names two files. A rotation into a file that is not there is a no-op."""
    assert ACTIVE.exists(), f"active roadmap missing: {ACTIVE}"
    assert ARCHIVE.exists(), f"roadmap archive missing: {ARCHIVE}"


def test_the_rotation_does_not_shrink_the_denominator():
    """Active + archive must conserve every item. Moving is not deleting.

    This is the whole point of the two-file split: a percentage computed over a
    set that quietly loses members reports progress that never happened.
    """
    a_open, a_done = _counts(ACTIVE)
    r_open, r_done = _counts(ARCHIVE)
    total = a_open + a_done + r_open + r_done
    assert total >= _TOTAL_ITEMS_FLOOR, (
        f"the two roadmap files now hold {total} items, below the {_TOTAL_ITEMS_FLOOR} "
        f"measured at the split (actif {a_open + a_done}, archive {r_open + r_done}). "
        "An item was deleted rather than rotated — or a floor was lowered to hide it."
    )


def test_the_archive_holds_nothing_actionable():
    """An open item in the archive is work nobody will look at again.

    `/resume` and `/sprint` read the active file only. An unchecked box that
    rotates out stops being scheduled without ever being decided.
    """
    r_open, _ = _counts(ARCHIVE)
    assert r_open == 0, (
        f"{r_open} unchecked item(s) in {ARCHIVE.name} — the archive is passive by "
        "contract. Move them back to checklist.md, or close them explicitly."
    )


def test_the_archive_keeps_what_was_delivered():
    """The archive is append-mostly. Losing history is how a class gets rediscovered."""
    _, r_done = _counts(ARCHIVE)
    assert r_done >= _ARCHIVE_DONE_FLOOR, (
        f"archive holds {r_done} delivered items, below the {_ARCHIVE_DONE_FLOOR} "
        "measured at the split — delivered work was erased, not archived."
    )


def test_the_active_file_stays_the_one_that_is_read():
    """Both files must name each other, or a reader lands on half the truth."""
    active_txt = ACTIVE.read_text(encoding="utf-8")
    archive_txt = ARCHIVE.read_text(encoding="utf-8")
    assert "archive.md" in active_txt, (
        "checklist.md never names archive.md — a reader cannot know the other half exists"
    )
    assert "checklist.md" in archive_txt, (
        "archive.md never names checklist.md — a reader landing here has no way back "
        "to what is actually open"
    )
