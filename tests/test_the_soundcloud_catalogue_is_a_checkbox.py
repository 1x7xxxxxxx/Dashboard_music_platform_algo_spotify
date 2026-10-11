"""R517 (X9 II) — SoundCloud « tout le catalogue » : a ticked checkbox, an empty picker,
and an age axis that reads oldest-first.

Type: Test
Uses: ast, src/dashboard/views/soundcloud.py
Depends on: nothing (pure functions + the view's source tree)
Persists in: nothing

What must hold:
1. no title is pre-selected (`release_picker(..., n=0)`) and the checkbox opens ticked;
2. the drawn titles: chosen chips win, else the whole catalogue when ticked, else none;
3. choosing a title unticks the catalogue ; ticking it clears the chips;
4. the age axis is reversed (the oldest title on the left).

Mutation record (2026-10-11): seen red with `n=0` → `n=len(titles)`, `chips` ignored in
catalogue_selection, the `_untick_catalogue` assignment removed, and the
`autorange="reversed"` call removed.
"""
from __future__ import annotations

import ast
from pathlib import Path

import streamlit as st

from src.dashboard.views import soundcloud as sc

_VIEW = Path(sc.__file__)


def _fn(name: str) -> ast.FunctionDef:
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def _kw(call: ast.Call) -> dict:
    return {k.arg: k.value for k in call.keywords}


def _calls(fn: ast.FunctionDef, attr: str) -> list[ast.Call]:
    return [n for n in ast.walk(fn) if isinstance(n, ast.Call)
            and (getattr(n.func, "attr", None) == attr or getattr(n.func, "id", None) == attr)]


def test_no_title_is_preselected_and_the_catalogue_opens_ticked() -> None:
    fn = _fn("_render_age_comparison")
    (picker,) = _calls(fn, "release_picker")
    n = _kw(picker)["n"]
    assert isinstance(n, ast.Constant) and n.value == 0
    (box,) = _calls(fn, "checkbox")
    v = _kw(box)["value"]
    assert isinstance(v, ast.Constant) and v.value is True


def test_the_drawn_titles() -> None:
    titles = ["new", "mid", "old"]
    assert sc.catalogue_selection(titles, True, []) == titles
    assert sc.catalogue_selection(titles, True, ["mid"]) == ["mid"]
    assert sc.catalogue_selection(titles, False, ["old"]) == ["old"]
    assert sc.catalogue_selection(titles, False, []) == []


def test_a_chip_unticks_the_catalogue_and_the_catalogue_clears_the_chips(monkeypatch) -> None:
    state: dict = {"cat": True, "pick": ["mid"]}
    monkeypatch.setattr(st, "session_state", state)
    sc._untick_catalogue("cat", "pick")
    assert state["cat"] is False
    state.update(cat=True)
    sc._clear_picks("cat", "pick")
    assert state["pick"] == []


def test_the_age_axis_reads_oldest_first() -> None:
    fn = _fn("_render_age_comparison")
    reversed_ = [c for c in _calls(fn, "update_xaxes")
                 if getattr(_kw(c).get("autorange"), "value", None) == "reversed"]
    assert reversed_, "the age axis is not reversed"
