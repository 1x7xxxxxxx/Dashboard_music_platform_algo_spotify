"""The home page never shows a literal `</div>`, and its ad block speaks in figures.

Type: Test
Uses: markdown_it (CommonMark, the grammar Streamlit's markdown follows), ast,
      streamlit.testing.v1.AppTest, src.dashboard.views.home / home_meta_advice
Depends on: utils.source_freshness.freshness_tile_html, utils.stat_boxes, views.home_meta_advice;
            the full-home render needs a provisioned Postgres on 5433 (skipped otherwise)
Persists in: nothing

R346 (owner's screen review, 2026-10-04):
(a) a literal `</div>` under every tile of « Collecte automatique » / « À déposer
    toi-même ». The divergence line, "" in the usual case, sat alone on its line in a
    multi-line HTML f-string: the line became blank, CommonMark closed the HTML block
    there and the indented `</div>` after it became an indented code block — text on
    screen. The tests below PARSE the produced HTML with a CommonMark parser instead of
    looking for a form in the source: the property is « no `</div>` reaches the page as
    text », and a blank line is only its most common cause.
(c) « Ce que ta publicité a appris » as metric boxes (`utils.stat_boxes`), not
    sentences — same `side` figures, same source.

The sibling sweep and the static guard over every `unsafe_allow_html` literal live in
`tests/test_an_html_placeholder_never_stands_alone_on_its_line.py`.

Mutation record (2026-10-04):
- `freshness_tile_html` joining its parts with "\\n\\n" → red (3 cases):
  test_a_freshness_tile_has_no_blank_line_whatever_its_parts, and
  test_the_rendered_home_shows_no_closing_tag_as_text. The CommonMark test stayed
  GREEN, and rightly: every part starts with a tag at column 0, so each blank line opens
  a new HTML block and nothing reaches the page as text.
- joining with "\\n\\n        " (blank line + indent, the real pre-R346 shape) → red: the
  three above AND test_commonmark_renders_no_closing_tag_of_a_freshness_tile_as_text.
- the builder's whitespace collapse removed (`e = _html.escape`) → red:
  test_a_freshness_tile_has_no_blank_line_whatever_its_parts (the "\\n\\n" label case).
- home.py freshness tile reverted to the pre-R346 f-string with `{_divergence}` alone on
  its line → red: test_the_rendered_home_shows_no_closing_tag_as_text (AppTest, live DB)
  and the static guard test_no_markdown_html_block_can_render_a_blank_line.
- `render_meta_advice` emitting the old sentence (`st.markdown(...)` of « Tu as dépensé
  … ») instead of `stat_row(_boites(...))` → red:
  test_the_ad_block_is_rendered_as_metric_boxes and
  test_the_ad_block_renderer_routes_its_figures_through_stat_row.
"""
from __future__ import annotations

import ast
import inspect
import re
import textwrap
from pathlib import Path

import pytest

import src.dashboard as _dashboard

markdown_it = pytest.importorskip("markdown_it")

_REPO = Path(_dashboard.__file__).resolve().parents[2]
_BLANK = re.compile(r"\n[ \t]*\n")
_AS_TEXT = "&lt;/div&gt;"


def _commonmark(html_src: str) -> str:
    """What a CommonMark renderer with raw HTML enabled makes of `html_src`."""
    return markdown_it.MarkdownIt("commonmark", {"html": True}).render(html_src)


def _tile(**over) -> str:
    from src.dashboard.utils.source_freshness import freshness_tile_html
    args = dict(color="#2ecc71", icon="🎧", label="Spotify for Artists", emoji="🟢",
                age_label="il y a 2 h", date_str="04/10/2026", when="chaque jour à 06:00",
                written="")
    args.update(over)
    return freshness_tile_html(**args)


# ── (a) the builder ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("over", [
    {},                                         # the usual case: no divergence
    {"written": "collecte du 03/10/2026"},       # the divergence line present
    {"label": "Meta\n\nAds"},                    # a value that carries a blank line
], ids=["no-divergence", "divergence", "value-with-blank-line"])
def test_a_freshness_tile_has_no_blank_line_whatever_its_parts(over) -> None:
    html_out = _tile(**over)
    assert not _BLANK.search(html_out), (
        f"the freshness tile renders a blank line ({over}): CommonMark closes the HTML "
        f"block there and the rest shows as text (R346).\n{html_out!r}")
    assert html_out.count("<div") == html_out.count("</div>")


@pytest.mark.parametrize("written", ["", "collecte du 03/10/2026"])
def test_commonmark_renders_no_closing_tag_of_a_freshness_tile_as_text(written) -> None:
    rendered = _commonmark(_tile(written=written))
    assert _AS_TEXT not in rendered and "<code>" not in rendered, (
        f"a CommonMark renderer shows part of the tile as text (written={written!r}):\n"
        f"{rendered}")


def test_the_parser_sees_the_defect_this_file_is_written_for() -> None:
    """The pre-R346 shape, rebuilt: if this went green the parser would prove nothing."""
    # Indented exactly like the f-string was: the closing tag is NOT at column 0, so
    # after the blank line CommonMark reads it as an indented code block.
    before = ('<div style="border:1px solid red;">\n'
              '                    <div>Spotify</div>\n'
              '                    <div>chaque jour à 06:00</div>\n'
              '                    {divergence}\n'
              '                </div>').format(divergence="")
    assert _AS_TEXT in _commonmark(before)


# ── (a) the whole home, rendered ─────────────────────────────────────────────

def _home_markdown_bodies() -> list[str]:
    from streamlit.testing.v1 import AppTest

    from tests.render_harness import SCRIPT
    at = AppTest.from_string(SCRIPT.format(root=str(_REPO), view="home"))
    at.run(timeout=180)
    assert not at.exception, f"home.show() raised: {at.exception}"
    return [str(m.value) for m in at.markdown]


def test_the_rendered_home_shows_no_closing_tag_as_text() -> None:
    from tests.db_gate import db_ready
    if not db_ready():
        pytest.skip("the full home render needs a provisioned Postgres on 5433")
    bodies = [b for b in _home_markdown_bodies() if "</div>" in b]
    assert bodies, "the home rendered no HTML tile at all — the test proves nothing"
    leaks = [b for b in bodies if _AS_TEXT in _commonmark(b) or _BLANK.search(b)]
    assert not leaks, (
        f"{len(leaks)} markdown element(s) of the home would show `</div>` as text "
        f"(R346). First one:\n{leaks[0][:400]!r}")


# ── (c) the ad block as metrics ──────────────────────────────────────────────

_SIDE = dict(meta_spend=3087.82, best_cpr=0.10899, best_cpr_name="Campagne A",
             best_cpr_spend=755.52, cash_sorti=3087.82, cash_rentre=None,
             axe_age=None, axe_pays=None, axe_placement=None)


def test_the_ad_block_is_rendered_as_metric_boxes() -> None:
    from streamlit.testing.v1 import AppTest

    src = (f"import sys; sys.path.insert(0, {str(_REPO)!r})\n"
           "import streamlit as st\n"
           "st.session_state['role']='artist'; st.session_state['artist_id']=1\n"
           "st.session_state['authenticated']=True; st.session_state['email']='a@t'\n"
           f"side = {_SIDE!r}\n"
           "from src.dashboard.views.home_meta_advice import render_meta_advice\n"
           "render_meta_advice(side)\n")
    at = AppTest.from_string(src)
    at.run(timeout=180)
    assert not at.exception, f"render_meta_advice raised: {at.exception}"
    rows = [str(m.value) for m in at.markdown if "flex-wrap" in str(m.value)]
    assert len(rows) == 1, "the ad figures are no longer ONE row of metric boxes"
    row = rows[0]
    flat = re.sub(r"\s", " ", row)  # thousands separator is a narrow no-break space
    for figure in ("3 088 €", "0,109 €", "—"):
        assert figure in flat, f"{figure!r} is missing from the metric row:\n{row[:600]}"
    assert row.count('border-radius:8px') == 3, "spent / back / best cost: three boxes"
    assert _AS_TEXT not in _commonmark(row)


def test_the_ad_block_renderer_routes_its_figures_through_stat_row() -> None:
    from src.dashboard.views import home_meta_advice
    tree = ast.parse(textwrap.dedent(inspect.getsource(home_meta_advice.render_meta_advice)))
    called = {getattr(n.func, "id", getattr(n.func, "attr", ""))
              for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert {"stat_row", "_boites"} <= called, (
        "render_meta_advice no longer draws its figures through stat_row(_boites(...)) — "
        "the owner asked for metrics, not sentences (R346).")
