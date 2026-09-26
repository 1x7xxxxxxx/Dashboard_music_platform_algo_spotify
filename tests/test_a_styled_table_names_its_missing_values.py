"""A styled table says what an absent value is, instead of crashing on it.

Type: Sub
Uses: .claude/hooks/lint_dashboard_view.py (its `unprotected_formats`), src/dashboard/views/
Depends on: nothing — no database, no Streamlit
Persists in: nothing

Class `df-na-rep`. `Styler.format` raises on None rather than rendering an empty cell,
and the NULL only appears when a LEFT JOIN misses — which development data usually
does not. The class was held by a PostToolUse hook that WARNS (exit 0) and by a shell
signature (`grep … | grep -v na_rep`) that a comment naming `na_rep` on the same line
satisfies. This file runs the hook's own tree predicate over every view, and blocks.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_HOOK = _ROOT / ".claude" / "hooks" / "lint_dashboard_view.py"
_VIEWS = _ROOT / "src" / "dashboard" / "views"


def _hook():
    spec = importlib.util.spec_from_file_location("lint_dashboard_view", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_view_formats_a_table_without_saying_what_an_absence_is() -> None:
    unprotected_formats = _hook().unprotected_formats
    offenders = []
    for path in sorted(_VIEWS.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        offenders += [f"{path.relative_to(_ROOT).as_posix()}:{line}"
                      for line in unprotected_formats(path.read_text(encoding="utf-8"))]
    assert not offenders, (
        "`.style.format(...)` sans `na_rep` : la première ligne NULL — un LEFT JOIN qui "
        "ne trouve rien, ce que les données de développement ne produisent presque "
        "jamais — fait lever la page chez l'artiste. Passe `na_rep=\"—\"` :\n  "
        + "\n  ".join(offenders))


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: an unprotected `.style.format` is named even when a comment on the
    same line says `na_rep` — the shape that satisfies the shell signature; the call
    that passes `na_rep=` is not, nor is a plain `str.format`, nor a file mid-edit."""
    unprotected_formats = _hook().unprotected_formats
    bad = ("def show(df):\n"
           "    st.dataframe(df.style.format('{:.0f}'))  # TODO na_rep\n")
    assert unprotected_formats(bad) == [2]
    good = "st.dataframe(df.style.format('{:.0f}', na_rep='—'))\n"
    plain = "label = '{} vues'.format(n)\n"
    assert unprotected_formats(good) == []
    assert unprotected_formats(plain) == []
    assert unprotected_formats("def show(:\n") == []
