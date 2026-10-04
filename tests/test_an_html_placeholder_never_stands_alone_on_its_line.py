"""A markdown HTML block can never render a blank line, whatever its placeholders hold.

Type: Hook
Uses: ast over src/dashboard
Depends on: nothing (no database)
Persists in: nothing

R346 (2026-10-04). The home tiles « Collecte automatique » / « À déposer toi-même »
showed a literal `</div>` under every tile. The f-string passed to
`st.markdown(..., unsafe_allow_html=True)` had `{_divergence}` alone on its line, and
`_divergence` is "" in the usual case: the line became blank, CommonMark ended the HTML
block there, and the indented `</div>` after it rendered as text.

The property is « no rendered line can become blank ». The first version of this guard
looked for the FORM (a line made of one placeholder and whitespace); it missed two
writings of the same property — a line of two placeholders (`{a}{b}`) and a literal
blank line. The predicate is now the property itself: rebuild the literal with EVERY
placeholder empty and look for a blank line. A placeholder glued to a tag
(`<div>{x}</div>`) leaves `<div></div>`, never a blank line — so it is not flagged.

Sweep (2026-10-04, R346): 19 `unsafe_allow_html=True` markdown calls in src/dashboard
→ 15 excluded (single-line HTML from concatenation, a helper or a constant: no newline
literal) → 4 multi-line f-strings → 1 live (home.py freshness tile, fixed and now a pure
single-line builder `views.home.freshness_tile_html`), 3 with every placeholder glued
inside a tag (home.py DAG grid, home_tiles.py total banner, useful_links.py `_card`).

Mutation record (2026-10-04): the pre-R346 tile (`{_divergence}` alone on its line) put
back in home.py → red at home.py:163; `{_divergence}{"" if _written else ""}` on that
line → red here, while the previous lone-placeholder regex returned [] on the same file;
`{a}{b}` and a literal blank line → red in the detector self-test.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import src.dashboard as _dashboard

ROOT = Path(_dashboard.__file__).resolve().parents[1]  # src/ — every markdown caller
_BLANK = re.compile(r"\n[ \t]*\n")


def _is_unsafe_markdown(call: ast.Call) -> bool:
    name = getattr(call.func, "attr", "")
    return name == "markdown" and any(
        k.arg == "unsafe_allow_html" and getattr(k.value, "value", False) is True
        for k in call.keywords)


def _literal_with_empty_placeholders(arg: ast.expr) -> str | None:
    """The string the call renders when every placeholder is "" — None if not literal."""
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.JoinedStr):
        return "".join(v.value for v in arg.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return None


def offenders(source: str, label: str = "<src>") -> list[str]:
    """Every markdown HTML literal that renders a blank line with empty placeholders."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and _is_unsafe_markdown(node) and node.args):
            continue
        text = _literal_with_empty_placeholders(node.args[0])
        if text is None or "<" not in text:
            continue
        m = _BLANK.search(text)
        if m:
            line = node.args[0].lineno + text.count("\n", 0, m.start()) + 1
            out.append(f"{label}:{line}")
    return out


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    bad = ('st.markdown(f"""<div>\n    <b>x</b>\n    {extra}\n</div>""", '
           'unsafe_allow_html=True)\n')
    assert offenders(bad) == ["<src>:3"]
    two = ('st.markdown(f"""<div>\n    <b>x</b>\n    {a}{b}\n</div>""", '
           'unsafe_allow_html=True)\n')
    assert offenders(two) == ["<src>:3"], "two placeholders alone are the same defect"
    blank = 'st.markdown("""<div>\n    <b>x</b>\n\n</div>""", unsafe_allow_html=True)\n'
    assert offenders(blank) == ["<src>:3"], "a literal blank line is the same defect"
    glued = ('st.markdown(f"""<div>\n    <b>x</b>{extra}\n</div>""", '
             'unsafe_allow_html=True)\n')
    assert offenders(glued) == []
    inline = 'st.markdown(f"""<div>\n    <span>{extra}</span>\n</div>""", unsafe_allow_html=True)\n'
    assert offenders(inline) == []
    escaped = 'st.markdown(f"""<div>\n    {extra}\n</div>""")\n'
    assert offenders(escaped) == [], "without unsafe_allow_html the HTML is escaped anyway"


def test_no_markdown_html_block_can_render_a_blank_line() -> None:
    found = []
    for path in sorted(ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "unsafe_allow_html" in text:
            found += offenders(text, str(path.relative_to(ROOT.parent)))
    assert not found, (
        f"{found} — a markdown HTML block renders a blank line when its placeholders are "
        "\"\": CommonMark closes the HTML block there and the rest (`</div>`) renders as "
        "text (R346). Glue each placeholder to a tag, or build the HTML on one line.")
