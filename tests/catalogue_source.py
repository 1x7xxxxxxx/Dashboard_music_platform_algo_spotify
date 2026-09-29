"""The ONE reader of `.claude/dev-docs/error-classes.md` signatures for the tests.

Type: Utility
Uses: .claude/dev-docs/error-classes.md
Depends on: nothing

R325 (2026-09-29): two guards read the catalogue's `- signature:` lines, each its own way.
The catalogue is Markdown, not Python, so reading it as text is the right tool — held here
once, like `tests/nav_source.py` holds the menu declaration.
"""
import re
from pathlib import Path

CATALOGUE = Path(__file__).resolve().parents[1] / ".claude/dev-docs/error-classes.md"


def signatures(text: str | None = None) -> dict[str, str]:
    """{class id: signature} for every class whose signature is one backquoted command."""
    text = CATALOGUE.read_text(encoding="utf-8") if text is None else text
    out, cid = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            cid = line[3:].strip()
        m = re.match(r"^- signature: `(.+)`\s*$", line)
        if m and cid:
            out[cid] = m.group(1)
    return out
