"""Guard: the architecture Views Map names every view that exists.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `views-map-drifts-from-the-views`.

`CLAUDE.md` has carried the sentence "La Views Map a déjà divergé deux fois sans que
rien ne le signale" since 2026-08-21. Measured 2026-08-28: it had drifted a third time.
**15 of 44 views were absent** — `onboarding`, `onboarding_health`, `db_health`,
`meta_cpr_optimizer`, `sacem`, `data_wrapped`, `account`, `referral`, `upgrade`,
`register`, `privacy`, `usage_analytics`, `etl_logs`, `referral_admin`, `promo_admin` —
a third of the dashboard, including two of the three surfaces an artist meets first.

Rule 18 asks for a `code-architecture-reviewer` spawn past five module changes. That is
a review, and a review is a thing someone has to remember to ask for; three drifts
happened while it existed. This asks the question mechanically, on every run.

It checks **presence, not prose**: whether each view is named at all, never whether its
description is good. A guard that tried to judge the description would either be
unfalsifiable or would fail on every honest edit, and this file would be deleted within
a week. Presence is the property that actually rotted.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test")


REPO = _repo_root()
ARCH = REPO / ".claude" / "dev-docs" / "architecture.md"
VIEWS_DIR = REPO / "src" / "dashboard" / "views"

# Not views: the package marker, and `home/`-style internals are covered by their
# package name. Anything else under views/ is a page and belongs in the map.
_NOT_A_VIEW = {"__init__", "__pycache__"}


def _views() -> set[str]:
    return {
        p.stem if p.is_file() else p.name
        for p in VIEWS_DIR.iterdir()
        if (p.is_file() and p.suffix == ".py") or (p.is_dir() and (p / "__init__.py").exists())
    } - _NOT_A_VIEW


def _views_map_text() -> str:
    """The `## Dashboard Views Map` section only — not the whole document.

    Scoped deliberately. Several of these names also appear elsewhere in
    architecture.md (data-flow prose, the DAG table), so searching the full file would
    make the guard pass on views the map itself never lists — the exact vacuity that
    let three drifts through.
    """
    text = ARCH.read_text(encoding="utf-8")
    m = re.search(r"^## Dashboard Views Map\s*$", text, re.M)
    assert m, "the `## Dashboard Views Map` heading is gone from architecture.md"
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


@pytest.mark.parametrize("view", sorted(_views()))
def test_every_view_is_named_in_the_views_map(view):
    body = _views_map_text()
    assert re.search(rf"`{re.escape(view)}(?:\.py|/)?`", body), (
        f"`{view}` exists under src/dashboard/views/ but the Dashboard Views Map in "
        f"architecture.md does not name it. Add a row: file, page name, data sources, "
        f"role. The map is what a reader consults instead of listing the directory — "
        f"a view missing from it is a view nobody knows to look at."
    )


def test_the_map_does_not_name_views_that_are_gone():
    """The other direction: a deleted view must not keep a row.

    Reads only the first column of each row, so a view named inside another row's
    prose (`saisie_s4a.py` mentions the deleted `reglages.py` on purpose, to record
    what replaced it) is not mistaken for a live entry.
    """
    first_cells = re.findall(r"^\| `([a-z_0-9]+)(?:\.py|/)?`", _views_map_text(), re.M)
    ghosts = sorted(set(first_cells) - _views())
    assert not ghosts, (
        f"the Views Map has rows for {ghosts}, which no longer exist under "
        "src/dashboard/views/. A map that points at deleted modules sends readers "
        "nowhere — the same thing the code graph does, and the reason CLAUDE.md says "
        "the graph orients but does not prove."
    )


def test_the_extraction_is_not_vacuous():
    """A section regex that matched nothing would make every check above pass."""
    body = _views_map_text()
    assert body.count("\n|") > 20, (
        f"the Views Map section yielded only {body.count(chr(10) + '|')} table rows. "
        "Either the map was gutted, or the heading match landed in the wrong place "
        "and the parametrised checks are asserting against an empty string."
    )
    assert len(_views()) > 20, "views/ yielded almost nothing — check the listing"
