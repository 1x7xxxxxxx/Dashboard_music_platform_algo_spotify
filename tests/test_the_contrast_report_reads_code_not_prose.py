"""R492 — the figure-contrast report reads the colours a figure DRAWS, not those its prose names.

Type: Test
Uses: tools/dev/figure_contrast_report (figures, _code_seul)

Before R492 a comment such as « # BON for the gain, #1DB954 like Spotify » added two
series colours to the figure below it : documenting a figure could fail the gate on a
figure that had not changed. Both halves are held — prose adds nothing, and the same
colour written as code is still counted, so blanking cannot blind the report.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.dev.figure_contrast_report import _code_seul, figures  # noqa: E402

_PROSE = '''
def chart():
    """Gain in BON, loss in MAUVAIS, Spotify green #1DB954."""
    fig = go.Figure()  # BON against #E53935
    fig.add_trace(go.Bar(x=[1], y=[1], marker_color="#1E88E5"))
    return fig
'''

_CODE = '''
def chart():
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[1], y=[1], marker_color="#1E88E5"))
    fig.add_trace(go.Bar(x=[1], y=[2], marker_color=BON))
    return fig
'''


def _tree(tmp_path: Path, source: str) -> Path:
    views = tmp_path / "src" / "dashboard" / "views"
    views.mkdir(parents=True)
    (tmp_path / "src" / "dashboard" / "utils").mkdir()
    (views / "v.py").write_text(source, encoding="utf-8")
    return tmp_path


def test_a_colour_named_in_a_comment_or_docstring_is_not_drawn(tmp_path):
    assert figures(_tree(tmp_path, _PROSE)) == [], "la prose a ajouté une couleur de série"


def test_the_same_colour_written_as_code_is_still_counted(tmp_path):
    found = figures(_tree(tmp_path, _CODE))
    assert len(found) == 1 and len(found[0]["couleurs"]) == 2, found


def test_blanking_keeps_every_line_number_and_the_string_literals():
    src = 'x = "#123456"  # #abcdef\n"""doc\n#fedcba"""\ny = 1\n'
    out = _code_seul(src)
    assert out.count("\n") == src.count("\n")
    assert '"#123456"' in out and "#abcdef" not in out and "#fedcba" not in out
    assert out.splitlines()[3] == "y = 1"
