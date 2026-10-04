"""Compact metric boxes rendered as ONE line of HTML — a figure without a `st.metric`.

Type: Utility
Uses: html (stdlib)
Depends on: nothing
Triggers: views/home_tiles.py (algorithm gates), views/home_meta_advice.py (ad metrics)
Persists in: nothing

Why not `st.metric`
-------------------
R346 (2026-10-04, owner's screen review): the `st.metric` value font was too big for the
three algorithm gates, and the ad block on the home page was prose where the owner wanted
numbers. `st.metric` has no size knob, and the first screen counts its gauges against a
ceiling (`.claude/dev-docs/first-screen-ceilings.json`). A small bordered box carries the
number at a readable size and stays out of that count by construction.

⚠️ The whole row is returned on a SINGLE line: a blank line inside an HTML block ends it
for CommonMark, and what follows renders as literal text (the `</div>` defect of R346,
guarded by `tests/test_an_html_placeholder_never_stands_alone_on_its_line.py`).
"""
from __future__ import annotations

import html


def _txt(s: str) -> str:
    """Text content: `<`, `>`, `&` escaped, quotes kept so names read as typed."""
    return html.escape(s, quote=False)


def stat_box(label: str, value: str, help_text: str = "", sub: str = "") -> str:
    """One bordered box: small label, the value, an optional small line under it. Pure."""
    sub_html = (f'<div style="font-size:0.72em; opacity:.7; margin-top:2px;">{_txt(sub)}</div>'
                if sub else "")
    return (f'<div title="{html.escape(help_text)}" style="flex:1 1 140px; min-width:0; '
            'border:1px solid rgba(128,128,128,.35); border-radius:8px; padding:6px 8px; '
            'text-align:center;">'
            '<div style="font-size:0.78em; opacity:.75; white-space:nowrap; overflow:hidden; '
            f'text-overflow:ellipsis;">{_txt(label)}</div>'
            f'<div style="font-size:1.05em; font-weight:600;">{_txt(value)}</div>'
            f'{sub_html}</div>')


def stat_row(boxes: list[str]) -> str:
    """Boxes side by side, wrapping on a narrow screen. Pure, single line."""
    return ('<div style="display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 8px 0;">'
            + "".join(boxes) + "</div>")
