"""R475 — the source grid shows no `</div>` as text where it LIVES, for an artist.

Type: Test
Uses: markdown_it (CommonMark), streamlit.testing.v1.AppTest, tests.render_harness.TENANT_SCRIPT,
      src.dashboard.views.onboarding_health -> utils.source_freshness
Depends on: a provisioned Postgres on 5433 (skipped otherwise)
Persists in: nothing

W1 (owner's voice notes, 2026-10-09): « erreurs /div sous ce qui alimente tes chiffres ».
The cause was R346 (a blank line inside a multi-line HTML f-string), fixed on 2026-10-04.
Its rendered guard, `test_the_home_never_shows_a_literal_closing_tag.py`, renders the HOME
as ADMIN — but R373 (2026-10-05) moved the grid to Santé onboarding, and only for an
artist. The guard kept passing on a page that no longer draws its subject. This one renders
the page the grid is on, as the reader who sees it, and first proves the grid is there.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import src.dashboard as _dashboard

markdown_it = pytest.importorskip("markdown_it")

_REPO = Path(_dashboard.__file__).resolve().parents[2]
_TILE = "border-radius:8px; padding:8px 6px"     # freshness_tile_html's outer div


def _bodies(view: str, artist_id: int) -> list[str]:
    from streamlit.testing.v1 import AppTest

    from tests.render_harness import TENANT_SCRIPT
    at = AppTest.from_string(TENANT_SCRIPT.format(root=str(_REPO), view=view,
                                                  artist_id=artist_id))
    at.run(timeout=180)
    assert not at.exception, f"{view}.show() raised: {at.exception}"
    return [str(m.value) for m in at.markdown] + [str(c.value) for c in at.caption]


@pytest.mark.xdist_group("onboarding_health")
def test_the_source_grid_shows_no_closing_tag_as_text_for_an_artist() -> None:
    from tests.db_gate import db_ready
    if not db_ready():
        pytest.skip("the onboarding render needs a provisioned Postgres on 5433")
    bodies = _bodies("onboarding_health", 1)
    assert any(_TILE in b for b in bodies), \
        "no freshness tile rendered — the grid moved again and this test proves nothing"
    md = markdown_it.MarkdownIt("commonmark", {"html": True})
    leaks = [b for b in bodies if "&lt;/" in md.render(b)]
    assert not leaks, (f"{len(leaks)} element(s) would show a closing tag as text. "
                       f"First:\n{leaks[0][:400]!r}")
