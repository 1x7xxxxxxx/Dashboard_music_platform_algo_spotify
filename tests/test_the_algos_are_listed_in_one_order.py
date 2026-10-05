"""The three algorithmic playlists read DW → Radio → RR everywhere, from ONE constant (R380).

Type: Guard
Uses: src/ (AST), src.utils.algo_order.ALGO_ORDER (re-exported by algo_knowledge),
      src.dashboard.views.trigger_algo._sections
Depends on: nothing
Persists in: nothing

Owner's screen review (2026-10-05): the verdict listed DW · RR · Radio, the budget
RR · DW · Radio — the same three playlists shuffled from one block to the next. A sweep
found 37 sequences written by hand, in every spelling (codes, `dw_probability`,
`dw_classifier`, full names). The property held: no sequence literal under `src/`
enumerates the three algos — an order is read from `ALGO_ORDER`. A dict used as a lookup
is not an order and stays allowed.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_HOME = Path("src/utils/algo_order.py")
# An ORDER names the algos themselves — by code or by the name the artist reads. A list
# of COLUMN names (`dw_probability`, `dw_p`) is a SQL/frame shape, not a display order,
# unless it is paired with the display name (`("dw_classifier", "Discover Weekly")`).
_BARE = (
    ("DW", re.compile(r"^(dw|discover[ _]weekly)$", re.I)),
    ("RADIO", re.compile(r"^radio$", re.I)),
    ("RR", re.compile(r"^(rr|release[ _]radar)$", re.I)),
)
_KEYED = (
    ("DW", re.compile(r"^dw_", re.I)),
    ("RADIO", re.compile(r"^radio_", re.I)),
    ("RR", re.compile(r"^rr_", re.I)),
)


def _match(node: ast.AST, family) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        for code, pattern in family:
            if pattern.match(node.value.strip().replace("\n", " ")):
                return code
    return None


def _algo_of(node: ast.AST) -> str | None:
    if isinstance(node, (ast.Tuple, ast.List)) and node.elts:
        first = node.elts[0]
        named = len(node.elts) > 1 and _match(node.elts[1], _BARE)
        return _match(first, _BARE) or (named and _match(first, _KEYED)) or None
    return _match(node, _BARE)


def _hand_orders():
    for path in sorted(Path("src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Tuple, ast.List)):
                algos = [_algo_of(e) for e in node.elts]
                if {"DW", "RR", "RADIO"} <= set(algos):
                    yield path, node.lineno, [a for a in algos if a]


def test_no_sequence_enumerates_the_three_algos_by_hand() -> None:
    sites = [f"{p}:{line} {order}" for p, line, order in _hand_orders()
             if not (p == _HOME and order == ["DW", "RADIO", "RR"])]
    assert not sites, (
        "a sequence lists the three algos by hand — read the order from "
        f"`src.utils.algo_order.ALGO_ORDER` (DW → Radio → RR): {sites}")


def test_the_one_order_is_the_owners() -> None:
    from src.dashboard.utils.algo_knowledge import ALGO_ORDER, populated_algos

    assert ALGO_ORDER == ("DW", "RADIO", "RR")
    assert populated_algos() == [a for a in ALGO_ORDER if a in populated_algos()]


def test_the_guide_names_only_the_parts_the_page_has() -> None:
    import src.dashboard.views.trigger_algo.router as router
    from src.dashboard.views.trigger_algo._sections import PAGE_SECTIONS, guide_sections_md

    md = guide_sections_md()
    assert [line for line in md.splitlines() if line.startswith("- ")] == [
        f"- **{fr}** — {dfr}" for _k, _key, fr, _dk, dfr in PAGE_SECTIONS]
    src = Path(router.__file__).read_text(encoding="utf-8")
    assert "st.tabs(section_labels())" in src or "section_labels()" in src, (
        "the layout no longer reads the parts the guide lists")
    assert "onglet" not in md.lower()
