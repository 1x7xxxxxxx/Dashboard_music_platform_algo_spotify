"""The catalogue's index is its documented entry point — and it had stopped listing.

`.claude/dev-docs/error-classes.md` opens with an Index table that `/sweep`, the
curator and any human read first. Measured 2026-08-21: the file held **63** class
entries and the index listed **51**. The twelve missing ones are the twelve most
recent — every class written since the index was last updated by hand, including
four written the same day.

Nothing failed, which is the point: appending an entry and forgetting the row is
invisible, and the omission is silent in exactly the direction that matters — a
reader scanning the index concludes the class does not exist and writes it again.

Error class: catalogue-index-omits-its-own-entries.
"""

from __future__ import annotations

import re
from pathlib import Path

CATALOGUE = Path(__file__).resolve().parent.parent / ".claude/dev-docs/error-classes.md"


def _index_and_entries() -> tuple[set[str], list[str]]:
    src = CATALOGUE.read_text(encoding="utf-8")
    start = src.index("## Index")
    end = src.index("\n---\n", start)
    index = set(re.findall(r"^\| \[([a-z0-9-]+)\]", src[start:end], re.M))
    # Entries are the `## class-id` headings AFTER the index block, so the schema
    # section and the index heading itself cannot be counted as classes.
    entries = re.findall(r"^## ([a-z0-9-]+)$", src[end:], re.M)
    return index, entries


def test_every_class_in_the_file_is_listed_in_the_index() -> None:
    index, entries = _index_and_entries()
    assert entries, "no class entries parsed — the parser is looking in the wrong place"
    missing = [e for e in entries if e not in index]
    assert not missing, (
        f"{len(missing)} class(es) exist in the catalogue but are absent from its "
        f"Index table: {missing}. A reader scanning the index concludes they do not "
        "exist and catalogues the same defect a second time."
    )


def test_the_index_lists_nothing_that_has_no_entry() -> None:
    """The other direction: a row pointing at an anchor that was renamed or removed."""
    index, entries = _index_and_entries()
    orphans = sorted(i for i in index if i not in entries)
    assert not orphans, (
        f"Index rows with no matching entry: {orphans}. The anchor link is dead and "
        "the class reads as catalogued while nothing describes it."
    )
