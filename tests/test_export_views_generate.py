"""Clicking "generate" on the two export views, which nothing else does.

Installed 2026-08-21 alongside the `db2` removal (roadmap R9).

Both export views opened a second connection inside `if generate_clicked:` — the
fallback cross-cutting rule #9 forbids by name, with `db` still open a few lines
above (and, in `export_pdf`, already handed in as a parameter). Removing it is a
small change on a path that **nothing covered**:

  * `test_views_render_smoke` renders `show()` but never presses a button, so the
    whole `generate_clicked` branch is invisible to it;
  * `test_csv_exporter` exercises `export_excel` / `export_all` directly with a
    mock, so it never sees the view's call site.

Between the two, the edited lines had no coverage at all. That is precisely the
shape of the `/kpis` and `/youtube/videos` regressions: fully mocked tests, green,
and a 500 in production.

These press the button.
"""
from __future__ import annotations

import os

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"
st.session_state["artist_id"] = 1
st.session_state["email"] = "admin@test"
st.session_state["authenticated"] = True
from src.dashboard.views.{view} import show
show()
"""


def _app(view: str):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), view=view))
    at.run(timeout=90)
    return at


def _fail_on_exception(at, view: str, when: str):
    if at.exception:
        ex = at.exception[0]
        detail = getattr(ex, "value", ex)
        pytest.fail(f"{view} raised {type(detail).__name__} {when}: {detail}")


@pytest.mark.parametrize("view", ["export_csv", "export_pdf"])
def test_pressing_generate_does_not_raise(view):
    """The branch that used to open `db2`.

    An empty tenant produces an empty export, not an exception — that is the
    point: the view must survive the click whether or not there is data behind it.
    """
    at = _app(view)
    _fail_on_exception(at, view, "on first render")

    if not at.button:
        pytest.skip(f"{view} exposes no button in this session — nothing to press")

    # The generate button is the primary one; fall back to the first if the view
    # ever stops marking it.
    target = next((b for b in at.button if getattr(b, "type", None) == "primary"),
                  at.button[0])
    target.click().run(timeout=120)
    _fail_on_exception(at, view, "after clicking generate")


@pytest.mark.parametrize("view", ["export_csv", "export_pdf"])
def test_the_view_no_longer_opens_a_second_connection(view):
    """The regression itself, stated where a reader of this file will look.

    `test_view_connection_budget` holds the repo-wide ceiling; this says the
    specific thing about the specific views whose click path is exercised above.
    """
    from pathlib import Path

    src = (Path(os.getcwd()) / "src" / "dashboard" / "views" / f"{view}.py").read_text(
        encoding="utf-8"
    )
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "db2" not in code, (
        f"{view} opens a `db2` again. Rule #9 names this case: one connection per "
        "show(), never a second as a fallback inside the same function."
    )
