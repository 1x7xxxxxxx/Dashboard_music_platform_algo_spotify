"""A placeholder in a markdown HTML block never stands alone on its line.

Type: Hook
Uses: ast over src/dashboard
Depends on: nothing (no database)
Persists in: nothing

R346 (2026-10-04). The home tiles « Collecte automatique » / « À déposer toi-même »
showed a literal `</div>` under every tile. The f-string passed to
`st.markdown(..., unsafe_allow_html=True)` had `{_divergence}` alone on its line, and
`_divergence` is "" in the usual case: the line became blank, CommonMark ended the HTML
block there, and the indented `</div>` after it rendered as text.

The property is « no rendered line can become blank », and the form that breaks it is a
line made of ONE placeholder and whitespace. A placeholder glued to a tag
(`<div>{x}</div>`) has the shape of the class without the property: an empty value leaves
`<div></div>`, not a blank line — so it is not flagged (sibling sweep, 1 live site of 4
multi-line candidates).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ALONE = re.compile(r"^\s*\{[^{}]+\}\s*$")


def _is_unsafe_markdown(call: ast.Call) -> bool:
    name = getattr(call.func, "attr", "")
    return name == "markdown" and any(
        k.arg == "unsafe_allow_html" and getattr(k.value, "value", False) is True
        for k in call.keywords)


def offenders(source: str, label: str = "<src>") -> list[str]:
    """Every markdown HTML f-string with a line that is a lone placeholder. Pure."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and _is_unsafe_markdown(node) and node.args):
            continue
        arg = node.args[0]
        if not isinstance(arg, ast.JoinedStr):
            continue
        segment = ast.get_source_segment(source, arg) or ""
        if "<" not in segment:
            continue
        for i, line in enumerate(segment.splitlines()[1:], start=arg.lineno + 1):
            if _ALONE.match(line):
                out.append(f"{label}:{i}: {line.strip()}")
    return out


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    bad = ('st.markdown(f"""<div>\n    <b>x</b>\n    {extra}\n</div>""", '
           'unsafe_allow_html=True)\n')
    assert offenders(bad) == ["<src>:3: {extra}"]
    glued = ('st.markdown(f"""<div>\n    <b>x</b>{extra}\n</div>""", '
             'unsafe_allow_html=True)\n')
    assert offenders(glued) == []
    inline = 'st.markdown(f"""<div>\n    <span>{extra}</span>\n</div>""", unsafe_allow_html=True)\n'
    assert offenders(inline) == []
    escaped = 'st.markdown(f"""<div>\n    {extra}\n</div>""")\n'
    assert offenders(escaped) == [], "without unsafe_allow_html the HTML is escaped anyway"


def test_no_markdown_html_block_can_render_a_blank_line() -> None:
    found = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "unsafe_allow_html" in text:
            found += offenders(text, str(path.relative_to(ROOT)))
    assert not found, (
        f"{found} — a placeholder alone on its line in a markdown HTML block: when it is "
        "\"\" the line is blank, CommonMark closes the HTML block and the rest (`</div>`) "
        "renders as text (R346). Glue the placeholder to the previous tag.")
