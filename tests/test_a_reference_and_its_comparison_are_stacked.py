"""R599 (owner, 2026-10-15) — a reference filter and its « comparer à » sit one ABOVE the
other, everywhere: the Meta bar stacks its campaign and second campaign, and the algo page
had the two release pickers side by side in `st.columns(2)`.

Type: Test
Uses: src/dashboard/views/trigger_algo/_tab_catalogue.py, src/dashboard/views/meta_creatives.py

The guard reads the STRUCTURE: a `selectbox` whose key names a comparison (`cmp`, `_b`,
`second`) must be called on `st` itself, never on a column handle. Blind to a pair drawn
through a helper that receives a column — said here rather than assumed away.
"""
import ast
import pathlib

_FILES = ("src/dashboard/views/trigger_algo/_tab_catalogue.py",
          "src/dashboard/views/meta_creatives.py")
_PAIRS = {"_tab_catalogue.py": ("cat_ref_", "cat_cmp_"),
          "meta_creatives.py": ("tl_creative", "tl_creative_b")}


def _selectboxes(path: str) -> list[tuple[int, str, str]]:
    """(line, receiver, key literal prefix) of each `<x>.selectbox(..., key=…)`. Pure."""
    out = []
    for node in ast.walk(ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "selectbox"):
            recv = node.func.value.id if isinstance(node.func.value, ast.Name) else "?"
            for kw in node.keywords:
                if kw.arg == "key":
                    v = kw.value
                    key = (v.value if isinstance(v, ast.Constant) else
                           "".join(p.value for p in v.values if isinstance(p, ast.Constant))
                           if isinstance(v, ast.JoinedStr) else "")
                    out.append((node.lineno, recv, key))
    return out


def test_the_reference_comes_first_and_both_are_stacked():
    for path in _FILES:
        ref_key, cmp_key = _PAIRS[pathlib.Path(path).name]
        boxes = _selectboxes(path)
        ref = [b for b in boxes if b[2] == ref_key]
        cmp_ = [b for b in boxes if b[2] == cmp_key]
        assert ref and cmp_, (path, boxes)
        assert ref[0][0] < cmp_[0][0], f"{path}: the reference comes first"
        side = [b for b in ref + cmp_ if b[1] != "st"]
        assert not side, f"{path}: drawn in a column, not stacked — {side}"
