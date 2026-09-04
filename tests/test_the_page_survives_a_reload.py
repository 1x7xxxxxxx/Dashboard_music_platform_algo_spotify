"""The active page must live in the URL, the way the language already does.

Type: Test
Uses: ast, streamlit.testing.v1.AppTest
Depends on: src/dashboard/app.py
Persists in: nothing

The defect
----------
Reported 2026-08-30: "je passe de FR à EN puis EN à FR sur la page Credentials API,
ça me ramène en page d'accueil".

Root cause, read in the code rather than guessed: `?page=` was consumed once and then
DELETED, so the active page existed only in `st.session_state['_nav_page']`. The
language, by contrast, had been given two durable carriers (the `?lang=` mirror, then
`saas_users.lang`). Any event that starts a fresh Streamlit session — a reload, a
WebSocket reconnect, a restored tab — therefore dropped the page and landed on home
while the language came back correctly. The asymmetry IS the bug.

I could not reproduce the bounce under AppTest, which models neither reloads nor
reconnects; what is asserted here is the property whose absence makes the bounce
possible, and which is worth holding on its own: an artist who reloads, bookmarks or
shares the URL of a page lands on that page.

The mirror needs `_page_mirrored`
---------------------------------
Without it, "the param differs from the active page" would also describe the rerun
that FOLLOWS a nav click — the URL still names the previous page at that instant — and
the stale param would overwrite the click. Remembering what the mirror itself wrote
separates "this is ours" from "someone opened a link".
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "src/dashboard/app.py"


def _source() -> str:
    return _APP.read_text(encoding="utf-8")


def test_the_active_page_is_written_back_to_the_url():
    src = _source()
    assert 'st.query_params["page"] = page' in src, (
        "app.py no longer mirrors the active page into ?page=. Without it the page "
        "lives only in session_state, and every reload or WebSocket reconnect lands "
        "the artist on home — while the language, which HAS a durable carrier, comes "
        "back correctly. That asymmetry is what was reported."
    )


def test_the_deep_link_is_no_longer_deleted_after_use():
    """`del st.query_params['page']` is what made the page unrecoverable."""
    tree = ast.parse(_source())
    deletes = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Delete)
        for tgt in n.targets
        if isinstance(tgt, ast.Subscript)
        and isinstance(tgt.slice, ast.Constant) and tgt.slice.value == "page"
    ]
    assert not deletes, (
        "app.py deletes the ?page= parameter again. It was removed on purpose: the "
        "delete existed so a deep link would not re-pin the page on every rerun, and "
        "the `_page_mirrored` bookkeeping now handles that without throwing the page "
        "away."
    )


def test_the_seed_is_conditioned_on_what_the_mirror_wrote():
    """Structural, not textual: the string `_page_mirrored` also lives in a comment.

    The first version of this assertion searched the file for that name and stayed
    GREEN through a mutation that removed the condition and kept the comment. What
    matters is that the assignment to `_nav_page` sits under an `if` whose test reads
    `_page_mirrored` — so the AST is the only honest place to ask.
    """
    tree = ast.parse(_source())

    seeds = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        for tgt in n.targets
        if isinstance(tgt, ast.Subscript)
        and isinstance(tgt.slice, ast.Constant) and tgt.slice.value == "_nav_page"
        and isinstance(n.value, ast.Name) and n.value.id == "_page_param"
    ]
    assert seeds, "app.py no longer seeds the active page from ?page= at all"

    parents = {id(c): p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}

    # Les VARIABLES dérivées de `_page_mirrored` : depuis le 2026-09-04 la condition
    # est nommée (`_own_mirror = _page_param == st.session_state.get('_page_mirrored')`)
    # parce qu'elle sert dans DEUX branches — celle qui honore le paramètre et celle
    # qui le jette ; ne la poser que dans la première a produit une régression.
    #
    # Le garde cherchait la CONSTANTE `"_page_mirrored"` dans le test du `if`. Il est
    # donc devenu rouge sur un code dont le comportement n'avait pas changé : ancré
    # sur la forme de la condition, pas sur la question « la graine est-elle
    # conditionnée ? ». Il suit maintenant le nom.
    mirror_vars = {
        tgt.id for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        for tgt in n.targets
        if isinstance(tgt, ast.Name)
        and any(isinstance(x, ast.Constant) and x.value == "_page_mirrored"
                for x in ast.walk(n.value))
    }

    def _guarded(node) -> bool:
        cur = node
        while cur is not None:
            parent = parents.get(id(cur))
            if isinstance(parent, ast.If) and any(
                (isinstance(x, ast.Constant) and x.value == "_page_mirrored")
                or (isinstance(x, ast.Name) and x.id in mirror_vars)
                for x in ast.walk(parent.test)
            ):
                return True
            cur = parent
        return False

    assert all(_guarded(n) for n in seeds), (
        "the ?page= seed is no longer conditioned on `_page_mirrored`. Reading the "
        "parameter unconditionally makes it win over a fresh nav click: on the rerun "
        "that follows the click the URL still names the PREVIOUS page, so the artist "
        "is sent straight back to it and the menu becomes unusable."
    )


def test_a_fresh_session_opening_a_page_url_lands_on_that_page():
    """The property itself, exercised: no session state, only the URL.

    The nav keys are resolved HERE and injected as a literal, instead of importing
    `src.dashboard.app` inside the AppTest script. That import pulls the whole
    dashboard into the test's script runner: fine serially, but under `-n auto` it
    blew past the 30 s timeout — the failure that this file's own Makefile change
    surfaced before CI could. The assertion is unchanged; only the accidental cost
    is gone.

    What this covers, stated plainly: the seeding RULE, re-expressed. The three tests
    above are what hold the real code to it; this one shows the rule produces the
    right landing for a session that has nothing but a URL.
    """
    from streamlit.testing.v1 import AppTest

    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.app import _NAV_SECTIONS

    nav_keys = sorted({key for _, _, items in _NAV_SECTIONS for _, key in items})
    assert "credentials" in nav_keys, "the credentials page left the navigation"

    script = f'''
import streamlit as st
_NAV_KEYS = {nav_keys!r}
_param = st.query_params.get("page")
if _param in _NAV_KEYS and _param != st.session_state.get("_page_mirrored"):
    st.session_state["_nav_page"] = _param
st.write("PAGE=", st.session_state.get("_nav_page"))
'''
    at = AppTest.from_string(script, default_timeout=30)
    at.query_params["page"] = "credentials"
    at.run()
    assert at.session_state["_nav_page"] == "credentials", (
        "a fresh session opening ?page=credentials did not land on credentials — "
        f"got {at.session_state['_nav_page']!r}. This is the reload case."
    )
