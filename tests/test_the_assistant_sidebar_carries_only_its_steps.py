"""The setup assistant, rendered: its sidebar is its two steps, its button stays inside.

Type: Test
Uses: streamlit.testing.v1.AppTest over the WHOLE app (`src.dashboard.app`, sidebar and
      view in the same run), `src.dashboard.app.sidebar_is_bare`, ast over
      `src.dashboard.views.onboarding` (source read through `inspect`)
Depends on: live Postgres (spotify_etl) for the rendered tests — they skip without it;
            the pure decision test runs everywhere
Persists in: nothing

R347 (2026-10-04, owner's screen review of « Mise en route »):

1. « On avait dit qu'on devait aller directement avec deux choix … Et là on peut voir
   toute l'app » — on the assistant the sidebar carries the two steps and NOT the menu
   (`render_navigation`), for every account, not only on the first login;
2. « Connecter mes sources … ça va directement dans Credential API. Mais normalement ça
   va sur Où tu en es » — the step-1 button sets step 2 and stays on the assistant;
3. « streaMLytics en bref » keeps one sentence: no figure, no legend.

Why rendered tests and not only the AST guards of
`tests/test_the_setup_assistant_is_two_steps_and_nothing_else.py`: the sidebar and the
view never render together in `test_views_render_smoke.py` (it calls `show()` alone),
and that is exactly where the step buttons and the menu meet. Each rendered test
carries its own CONTROL (the home page draws the menu; step 1 draws the button) so a
render that draws nothing cannot pass for a bare sidebar.

Mutation record (2026-10-04), each applied by a script, seen red, restored, seen
green again:
* `sidebar_is_bare` → `page == 'onboarding' and bool(st.session_state.get(
  FIRST_RUN_FOCUS))` (the pre-R347 first-login-only rule):
  `test_the_bare_sidebar_is_decided_by_the_page_alone` and
  `test_the_assistant_sidebar_draws_no_navigation` RED;
* `render_navigation(...)` moved out of `if not _bare:` in `_main_body` (decision
  intact, wiring broken): `test_the_assistant_sidebar_draws_no_navigation` RED, the pure
  test GREEN — which is why both exist;
* the `_onb_go_creds` branch → `_goto('credentials')`:
  `test_connect_my_sources_opens_step_two_and_stays` RED;
* a plotly figure, then (separately) a numpy `st.image`, added under the « en bref »
  sentence: `test_the_brief_calls_no_figure` and
  `test_the_welcome_step_draws_no_figure` RED for both. The image mutation first
  stayed GREEN on the rendered test — AppTest reports `image`, not `imgs`.
"""
from __future__ import annotations

import ast
import inspect
import time


import src.dashboard.app as app_module
from src.dashboard.app import _NAV_SECTIONS, sidebar_is_bare
from tests.db_gate import requires_live_db

_APP = app_module.__file__

# Element types that draw a figure, as AppTest names them — each one SEEN on a probe
# render (2026-10-04): plotly_chart; image (st.image AND st.pyplot); vega_lite_chart
# (st.line_chart/bar_chart/altair_chart); graphviz_chart. `imgs`, the proto field name,
# is NOT what AppTest reports — with it the image mutation stayed green.
_FIGURES = ("plotly_chart", "image", "vega_lite_chart", "graphviz_chart")
# Streamlit calls that draw a figure — the AST side of the same question.
_FIGURE_CALLS = frozenset({
    "plotly_chart", "image", "pyplot", "altair_chart", "vega_lite_chart",
    "line_chart", "bar_chart", "area_chart", "scatter_chart", "map",
    "pydeck_chart", "graphviz_chart", "bokeh_chart"})


def _nav_keys() -> list[str]:
    return [key for *_, items in _NAV_SECTIONS for _, key in items]


def test_the_bare_sidebar_is_decided_by_the_page_alone() -> None:
    """Bare on the assistant, whatever the first-login flag; never bare elsewhere."""
    import streamlit as st
    from src.dashboard.app import FIRST_RUN_FOCUS

    keys = _nav_keys()
    assert "onboarding" in keys, "the assistant left the menu — this test lost its subject"
    for first_run in (False, True):
        st.session_state[FIRST_RUN_FOCUS] = first_run
        try:
            bare = {k for k in keys if sidebar_is_bare(k)}
        finally:
            st.session_state.pop(FIRST_RUN_FOCUS, None)
        assert bare == {"onboarding"}, (
            f"first_run={first_run}: the bare sidebar is decided for {sorted(bare)}; "
            "it must be the assistant and only the assistant (R347).")


def _configured_tenant() -> int:
    """A tenant whose setup is done — the case of the defect (first login hid it)."""
    from tests.test_every_step_of_the_assistant_is_reachable import (
        _configured_tenant as pick)
    return pick()


def _render(page: str):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(_APP, default_timeout=180)
    for key, value in {
        "authenticated": True, "role": "artist", "artist_id": _configured_tenant(),
        "username": "artist@test", "email": "artist@test", "name": "artist@test",
        "_last_activity": time.time(), "_nav_page": page,
    }.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, at.exception
    return at


def _menu_radios(at) -> list[str]:
    return [r.key for r in at.sidebar.radio if str(r.key or "").startswith("_nav_")]


@requires_live_db()
def test_the_assistant_sidebar_draws_no_navigation() -> None:
    home = _render("home")
    assert _menu_radios(home), (
        "CONTROL: the home page draws no menu radio — the probe cannot see "
        "`render_navigation`, so its absence on the assistant would prove nothing")

    at = _render("onboarding")
    assert not _menu_radios(at), (
        f"the assistant's sidebar draws the menu {_menu_radios(at)} — the artist sees "
        "the whole app beside the two steps (R347)")
    side_buttons = [b.key for b in at.sidebar.button]
    assert side_buttons and all(str(k).startswith("_onb_jump_") for k in side_buttons), (
        f"the assistant's sidebar carries {side_buttons}; only the step buttons belong")


@requires_live_db()
def test_connect_my_sources_opens_step_two_and_stays() -> None:
    at = _render("onboarding")
    assert at.session_state["_onboarding_step"] == 1, "the assistant did not open on step 1"
    button = [b for b in at.button if b.key == "_onb_go_creds"]
    assert button, "CONTROL: « 🔑 Connecter mes sources → » is not drawn on step 1"

    after = button[0].click().run()
    assert not after.exception, after.exception
    assert after.session_state["_page_rendered_last"] == "onboarding", (
        f"the button left the assistant for "
        f"{after.session_state['_page_rendered_last']!r} (R347: it leads to step 2)")
    assert after.session_state["_onboarding_step"] == 2, "the button did not set step 2"
    titles = " ".join(x.value for x in after.title)
    assert "Où tu en es" in titles or "Where you stand" in titles, (
        f"step 2 is set but the body shows {titles!r}")


def _brief_statements() -> list[ast.stmt]:
    """The statements of `_step_welcome` between the « en bref » and the offer titles."""
    from src.dashboard.views import onboarding

    tree = ast.parse(inspect.getsource(onboarding._step_welcome))
    body = tree.body[0].body
    marks = [i for i, s in enumerate(body)
             if any(isinstance(c, ast.Constant) and c.value in
                    ("onboarding.b1_title", "onboarding.b2_title")
                    for c in ast.walk(s))]
    assert len(marks) == 2, f"the « en bref » / offer titles moved: {marks}"
    return body[marks[0]:marks[1]]


def test_the_brief_calls_no_figure() -> None:
    """The source side, runs without a database."""
    calls = {getattr(c.func, "attr", getattr(c.func, "id", ""))
             for s in _brief_statements() for c in ast.walk(s)
             if isinstance(c, ast.Call)}
    assert "markdown" in calls, "CONTROL: the « en bref » slice holds no call at all"
    assert not calls & _FIGURE_CALLS, (
        f"« streaMLytics en bref » draws {sorted(calls & _FIGURE_CALLS)} again — it "
        "keeps one sentence, no figure, no legend (R347)")


@requires_live_db()
def test_the_welcome_step_draws_no_figure() -> None:
    """The rendered side: whatever function draws it, step 1 shows no figure."""
    at = _render("onboarding")
    assert at.session_state["_onboarding_step"] == 1, "CONTROL: not on the welcome step"
    drawn = {kind: len(at.main.get(kind)) for kind in _FIGURES}
    assert not any(drawn.values()), f"the welcome step draws figures: {drawn}"
