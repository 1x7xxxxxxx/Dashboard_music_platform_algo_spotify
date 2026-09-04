"""Guards: the setup assistant is reachable, on top, and it decides the landing.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Five defects, all reported from ONE real second login on the sandbox tenant
(2026-09-04), all of the same family — a surface that exists and that nothing leads to:

1. « c'est tout en bas du volet de navigation » — the `### Étapes` list was written by
   `views/onboarding.show()`, i.e. during the CONTENT phase, so it landed under the
   whole sidebar including the logout button.
2. « impossible de revenir aux différentes étapes de config » — the three steps were
   `st.markdown`. They NAMED the steps without leading to them. Exactly the defect the
   home page's four steps had, fixed there on 2026-08-30 for the same reason.
3. « je ne suis plus sur étapes 1 2 3 » — the landing router asked "has this artist
   declared NOTHING?" while the home page asked "is the setup FINISHED?". One declared
   identity was enough to make the assistant disappear at 1/4.
4. « il n'y a toujours pas d'onglet sélectionné dans le navigateur » — the init path set
   every section radio to `None`, so the menu highlighted nothing while the content
   rendered a page. `goto()` reproduced it on every programmatic navigation.
5. « remonter … artiste <nom> au niveau de votre plan : premium » — the two halves of
   the same identity sat at the two ends of the sidebar.

Each test below fails on the state of the code BEFORE the fix; each was verified red by
mutation, not assumed to be.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
APP = REPO / "src" / "dashboard" / "app.py"
ONB = REPO / "src" / "dashboard" / "views" / "onboarding.py"
AUTH = REPO / "src" / "dashboard" / "auth.py"
HOME = REPO / "src" / "dashboard" / "views" / "home.py"


def _fn(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == name), None)
    assert fn is not None, f"{path.name} no longer defines {name}()"
    return fn


def _call_lines(fn: ast.AST, name: str) -> list[int]:
    """Line numbers where `name` is called (bare or as an attribute)."""
    out = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if (isinstance(f, ast.Name) and f.id == name) or \
           (isinstance(f, ast.Attribute) and f.attr == name):
            out.append(node.lineno)
    return out


# ── 1. Position ───────────────────────────────────────────────────────────────

def test_the_step_list_is_drawn_before_the_navigation():
    """Above the menu, not under the logout button."""
    body = _fn(APP, "_main_body")
    steps = _call_lines(body, "render_sidebar_steps")
    nav = _call_lines(body, "render_navigation")
    assert steps, (
        "_main_body no longer draws the assistant's steps. They would go back to being "
        "written by views/onboarding.show(), i.e. after the entire sidebar."
    )
    assert nav, "_main_body no longer renders the navigation"
    assert min(steps) < min(nav), (
        "the step list is drawn after the navigation — it reads as a footer, which is "
        "exactly what was reported."
    )


def test_the_view_no_longer_writes_the_sidebar_itself():
    """One writer for that block. Two would put it in two places at once."""
    show = _fn(ONB, "show")
    sidebar_writes = [n.lineno for n in ast.walk(show)
                      if isinstance(n, ast.Attribute) and n.attr == "sidebar"]
    assert not sidebar_writes, (
        f"onboarding.show() writes st.sidebar at line(s) {sidebar_writes}. That runs in "
        "the content phase, so the block lands under the whole sidebar."
    )


def test_the_identity_block_carries_the_plan_and_is_drawn_before_the_nav():
    """« artiste <nom> » and « Votre plan » are one block, at the top."""
    auth_src = AUTH.read_text(encoding="utf-8")
    assert "nav.plan_badge_premium" in auth_src, (
        "the plan badge left show_user_sidebar(); the identity and its plan are back at "
        "the two ends of the sidebar."
    )
    assert "nav.plan_badge_premium" not in APP.read_text(encoding="utf-8"), (
        "the plan badge is rendered in app.py too — two surfaces, one fact.")
    body = _fn(APP, "_main_body")
    ident = _call_lines(body, "show_user_sidebar")
    nav = _call_lines(body, "render_navigation")
    assert ident and nav and min(ident) < min(nav), (
        "the identity block is drawn after the navigation — that is the bottom of the "
        "sidebar, which is what was reported."
    )


# ── 2. Reachability ───────────────────────────────────────────────────────────

def test_every_step_that_is_not_the_current_one_is_a_button():
    """A step you cannot click is a step you cannot go back to."""
    fn = _fn(ONB, "render_sidebar_steps")
    buttons = _call_lines(fn, "button")
    assert buttons, (
        "render_sidebar_steps draws no button: the three steps are text again, and "
        "« impossible de revenir aux différentes étapes de config » is back."
    )


def test_the_assistant_offers_a_way_into_the_app_and_a_way_to_stop_showing_it():
    """A screen you cannot leave is a door, not a help page."""
    fn = _fn(ONB, "_render_landing_choice")
    assert _call_lines(fn, "button"), "no way out of the setup page"
    assert _call_lines(fn, "checkbox"), (
        "no checkbox: the artist cannot decide to stop landing here.")
    assert _call_lines(fn, "set_show_on_login"), (
        "the checkbox is not persisted — a login preference that does not survive the "
        "login answers nothing."
    )


# ── 3. One definition of 'finished' ───────────────────────────────────────────

def test_the_landing_asks_whether_the_setup_is_FINISHED():
    src = ast.get_source_segment(
        APP.read_text(encoding="utf-8"), _fn(APP, "_first_run_landing")) or ""
    assert "read_setup_state" in src, (
        "the landing router no longer reads the shared completion state.")
    assert "artist_readiness" not in src, (
        "the router is back on artist_readiness, whose 'all todo' threshold means "
        "'has not STARTED' — one declared identity made the assistant disappear."
    )


def test_both_surfaces_read_the_same_completion_rule():
    """The home page's `{done}/4` and the landing must never disagree again."""
    for path in (APP, HOME):
        assert "setup_completion" in path.read_text(encoding="utf-8"), (
            f"{path.name} no longer goes through utils/setup_completion — the rule is "
            "being restated, which is how the two answers diverged."
        )


# ── 4. The menu agrees with the page ──────────────────────────────────────────

def test_the_menu_selection_is_reasserted_on_every_run():
    """Not only when the state is being repaired.

    `goto()` sets every section radio to None, and `goto` runs on a page whose key IS
    visible — so the repair branch never fires and the menu shows no selection at all.
    """
    fn = _fn(APP, "resolve_nav_page")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "_select_nav_radio"]
    assert calls, "resolve_nav_page never points the radios at the active page"
    # At least one call must sit at the function's TOP level — inside the `if` only
    # would mean "on repair only", which is the bug.
    top_level = []
    for stmt in fn.body:
        for node in ast.walk(stmt):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "_select_nav_radio"
                    and not isinstance(stmt, (ast.If, ast.Try, ast.For, ast.While))):
                top_level.append(node.lineno)
    assert top_level, (
        "_select_nav_radio is only called inside a conditional — after goto(), the "
        "condition is false and the menu highlights nothing."
    )


# ── 5. A view may navigate without crashing the page ──────────────────────────

NAV = REPO / "src" / "dashboard" / "utils" / "navigation.py"


def test_goto_does_not_write_widget_keys():
    """Error class: writing a widget's session key after the widget exists.

    `goto()` is called from VIEWS — the content phase — and the sidebar radios are
    instantiated before that. It used to set every `_nav_<section>` key to None, which
    Streamlit refuses:

        StreamlitAPIException: `st.session_state._nav_reports` cannot be modified
        after the widget with key `_nav_reports` is instantiated.

    So EVERY programmatic navigation from a view raised — the four home-page steps
    included. On the assistant it was masked by an early `?page=onboarding` route that
    rendered no sidebar at all; removing that route on 2026-09-04 is what exposed it,
    live in a browser.

    Menu/page agreement now belongs to `app.resolve_nav_page`, which runs before the
    widgets exist. Nothing else may touch those keys.
    """
    fn = _fn(NAV, "goto")
    writes = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "session_state"):
                continue
            key = target.slice
            # `_nav_page` is plain state, not a widget — it is the one legal write.
            if isinstance(key, ast.Constant) and key.value == "_nav_page":
                continue
            if isinstance(key, ast.Name) and key.id == "_PAGE_KEY":
                continue
            writes.append(ast.dump(key)[:60])
    assert not writes, (
        f"goto() writes session keys other than _nav_page: {writes}. Called from a "
        "view, that raises StreamlitAPIException on any key that is a widget's."
    )


def test_the_assistant_has_no_early_route_that_skips_the_sidebar():
    """`?page=onboarding` must render INSIDE the app shell, like every other page."""
    body = _fn(APP, "_main_body")
    src = ast.get_source_segment(APP.read_text(encoding="utf-8"), body) or ""
    head = src.split("_check_db_health")[0]
    assert "show_onboarding()" not in head, (
        "the early ?page=onboarding route is back: it renders the assistant alone and "
        "calls st.stop(), so the sidebar — steps, menu, identity — never renders. And "
        "because the URL mirror writes ?page=<page> on every run, that branch fires on "
        "every rerun once the assistant has been shown once."
    )
