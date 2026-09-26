"""A rendered figure is laid out: a row ends level, a title fits its column, labels and
legend stay clear of what they would cover.

Type: Sub
Uses: tests/render_harness.py (render_once → Fig facts, VIEWS)
Depends on: live Postgres (skipped without it, like the render smoke)
Persists in: nothing

R189 (2026-09-26). R188 shipped three layout defects that every test passed — a verdict
cut off, band labels printed on top of each other, a legend on the modebar — and the
owner's screen found them. The same day, rendering every view and reading the Plotly
specs found two more that had been live since 2026-09-22, then confirmed them in a
browser: the Wrapped row (400 | 260 | 260 px, a 43-character title 288 px wide in a
227 px column, a four-entry legend over that title) and the Spotify row (420 next to 380).

WHAT THIS IS — AND IS NOT
It is a lint on geometry ESTIMATED from the spec: a page width, a mean character width,
Plotly's default margins. It says « look at this », it does not say « this is right ».
Class `a-diagram-is-verified-by-looking-at-it` stays `manual`: nothing here judges what a
figure MEANS, and a figure that passes can still be misleading. Calibrated in the browser
on 2026-09-26: `meta_x_spotify`'s legend TOUCHES its title's box without covering a letter
— a DOM-overlap rule reported it, the eye did not; the rule below does not.

A per-view ceiling (`_KNOWN`) freezes what is left on the day it was written — each entry
names the site and why it stays. It can only go down.
"""
from __future__ import annotations

from collections import defaultdict

import pytest

from tests.db_gate import db_ready
from tests.render_harness import VIEWS, Fig, render_once

pytestmark = pytest.mark.skipif(not db_ready(), reason="rendered-figure lint needs the live DB")

PAGE_PX = 1000        # main area of a 1366 px laptop, wide layout, sidebar open
CHAR_PX = 6.5         # mean width of a 12 px Plotly label character
TITLE_EM = 0.55       # mean character width of a title, in ems of its font size
MODEBAR_PX = 180      # the modebar's width, top-right, shown on hover
DEFAULT_H = 450       # Plotly's height when none is set


def unequal_rows(figs: tuple[Fig, ...]) -> list[dict]:
    """Rows of `st.columns` whose columns hold figures of different heights."""
    rows: dict = defaultdict(dict)
    for f in figs:
        if f.row is not None:
            rows[f.row].setdefault(f.col, f.height or DEFAULT_H)
    return [dict(r) for r in rows.values() if len(r) >= 2 and len(set(r.values())) > 1]


def truncated_titles(figs: tuple[Fig, ...]) -> list[str]:
    """Titles whose longest line is wider than the figure's column."""
    out = []
    for f in figs:
        longest = max((len(line) for line in f.title.split("\n")), default=0)
        if longest * TITLE_EM * f.title_size > f.width * PAGE_PX - 20:
            out.append(f.title)
    return out


def overlapping_labels(figs: tuple[Fig, ...]) -> list[tuple[str, str]]:
    """Two annotations on the same line whose x distance is shorter than their text."""
    out = []
    for f in figs:
        plot_w = f.width * PAGE_PX - 160
        by_line: dict = defaultdict(list)
        for frac, line, text in f.annotations:
            if frac is not None and text:
                by_line[line].append((frac, text))
        for xs in by_line.values():
            xs.sort()
            for (fa, ta), (fb, tb) in zip(xs, xs[1:]):
                if (fb - fa) * plot_w < (len(ta) + len(tb)) / 2 * CHAR_PX:
                    out.append((ta, tb))
                    break
    return out


def legend_on_modebar(figs: tuple[Fig, ...]) -> list[int]:
    """A top horizontal legend reaching the modebar's corner (top 28 px, right side)."""
    return [f.legend_chars for f in figs
            if f.modebar and f.legend_top is not None and f.legend_top < 28
            and f.legend_chars * CHAR_PX > f.width * PAGE_PX - MODEBAR_PX]


_RULES = {"unequal_rows": unequal_rows, "truncated_titles": truncated_titles,
          "overlapping_labels": overlapping_labels, "legend_on_modebar": legend_on_modebar}

# What is left, and why. A ceiling, never a target.
_KNOWN: dict[tuple[str, str], int] = {
    # Empty on the day it was written: the five sites the render found were fixed and each
    # one LOOKED at in a browser at 1366 px (Wrapped row, Spotify row, the Meta verdict's
    # legend under the modebar).
}


def _fig(**kw) -> Fig:
    base = dict(row=None, col=None, width=1.0, height=380, title="", title_size=17,
                annotations=(), legend_top=None, legend_chars=0, modebar=True)
    base.update(kw)
    return Fig(**base)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Each rule bites on the exact R188/R189 defect and stays quiet on its fix."""
    row = (_fig(row=1, col=0, width=1 / 3, height=400), _fig(row=1, col=1, width=1 / 3, height=260))
    assert unequal_rows(row) and not unequal_rows(
        (row[0]._replace(height=320), row[1]._replace(height=320)))
    assert not unequal_rows((_fig(row=1, col=0, height=400), _fig(row=1, col=0, height=260))), (
        "two figures stacked in ONE column are not a row")

    long = _fig(width=1 / 3, title="Listeners · Streams · Saves · Playlist adds")
    assert truncated_titles((long,)) and not truncated_titles((long._replace(title="Volumes"),))
    assert not truncated_titles((long._replace(width=1.0),)), "full width is not truncated"

    bands = _fig(width=0.5, annotations=((0.40, "y domain:1", "Campagne printemps"),
                                         (0.43, "y domain:1", "Relance été")))
    assert overlapping_labels((bands,))
    apart = bands._replace(annotations=((0.1, "y domain:1", "Campagne printemps"),
                                        (0.8, "y domain:1", "Relance été")))
    assert not overlapping_labels((apart,))
    stacked = bands._replace(annotations=((0.40, "y domain:1", "Campagne printemps"),
                                          (0.43, "y domain:0.9", "Relance été")))
    assert not overlapping_labels((stacked,)), "labels on two lines do not collide"

    top = _fig(width=0.5, legend_top=9, legend_chars=59)
    assert legend_on_modebar((top,))
    assert not legend_on_modebar((top._replace(legend_top=None),)), "a legend below is clear"
    assert not legend_on_modebar((top._replace(modebar=False),)), "no modebar, no collision"


def test_the_ceiling_names_only_rules_that_exist() -> None:
    assert {rule for _v, rule in _KNOWN} <= set(_RULES)
    assert {v for v, _r in _KNOWN} <= set(VIEWS)


@pytest.mark.parametrize("view", [pytest.param(v, marks=pytest.mark.xdist_group(v))
                                  for v in VIEWS])
def test_a_rendered_figure_is_laid_out(view: str) -> None:
    rendu = render_once(view)
    if rendu.erreur:
        pytest.skip(f"{view} did not render — test_views_render_smoke reports it")
    over = {}
    for name, rule in _RULES.items():
        found = rule(rendu.figures)
        if len(found) > _KNOWN.get((view, name), 0):
            over[name] = found
    assert not over, (
        f"{view}: layout estimated from the rendered Plotly specs — LOOK at the page "
        f"before believing or dismissing it: {over}")
