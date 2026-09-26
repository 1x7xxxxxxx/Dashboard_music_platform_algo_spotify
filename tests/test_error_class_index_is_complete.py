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
import pytest

# Ce fichier ne lit QUE des documents : rien sous src/, airflow/ ni migrations/.
# `make test-fast` le saute, `make test-docs` ne lance que lui et ses pairs,
# `make test` et la CI le lancent toujours.
# Voir `.claude/dev-docs/test-suite-performance.md`.
pytestmark = pytest.mark.docs

CATALOGUE = Path(__file__).resolve().parent.parent / ".claude/dev-docs/error-classes.md"


def _index_and_entries(src: str | None = None) -> tuple[set[str], list[str]]:
    src = CATALOGUE.read_text(encoding="utf-8") if src is None else src
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


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity, both directions, on a fabricated catalogue: the 2026-08-21 shape (the
    newest entries absent from the index) and a dead index row are both seen; a class
    NAMED only in prose or in the schema section above the index is not an entry."""
    doc = ("# Catalogue\n## schema-field-names\n\n## Index\n\n"
           "| Class |\n|---|\n| [old-class](#old-class) |\n| [renamed-away](#renamed-away) |\n"
           "\n---\n\n## old-class\n- status: guarded\n\n## newest-class\n"
           "- status: open\n  see also ## not-a-heading-in-prose\n")
    index, entries = _index_and_entries(doc)
    assert entries == ["old-class", "newest-class"]
    assert [e for e in entries if e not in index] == ["newest-class"]
    assert sorted(i for i in index if i not in entries) == ["renamed-away"]
