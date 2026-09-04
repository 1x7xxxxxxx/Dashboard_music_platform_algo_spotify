"""The guides must RENDER right on both platforms, not merely resolve their tokens.

Installed 2026-08-21, closing the mechanical half of roadmap item R19.

`tests/test_os_hints.py` already proves a lot: no raw `Ctrl+U` survives in guide
content, every `{{TOKEN}}` used resolves, and the two OS renderings differ. All of
that is about the *resolver*. None of it renders a page.

The gap that leaves is the one the Grinch beta session actually fell into
(2026-08-12): a macOS artist read `Ctrl+U` and was stuck. A token can resolve
perfectly in a unit test and still reach the screen unresolved, because the view
forgot to call the resolver on that particular string — `credential_guides_st.py`
renders through `_os_md`, and a plain `st.markdown` next to it looks identical in
the source.

So this renders the credential guides through Streamlit's AppTest, once per OS,
and reads what actually came out:

  * no `{{TOKEN}}` reaches the page,
  * the macOS pass spells ⌘ and never a bare Windows `Ctrl+…`,
  * the Windows pass spells `Ctrl+…` and never ⌘.

R19 asked for "un passage visuel Mac/Windows sur les guides". A screenshot proves
it once; this proves it on every run.
"""
from __future__ import annotations

import os
import re

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

# The Windows spellings that must never survive a macOS render, and vice versa.
_WINDOWS_ONLY = re.compile(r"\bCtrl\+[A-Z0-9]|\bF12\b")
_MAC_ONLY = re.compile(r"⌘|Cmd\+")
_UNRESOLVED = re.compile(r"\{\{[A-Z_]+\}\}")

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"
st.session_state["artist_id"] = 1
st.session_state["email"] = "admin@test"
st.session_state["authenticated"] = True
st.session_state["_guide_os"] = {os_key!r}
from src.dashboard.views.credentials import show
show()
"""


def _render(os_key: str) -> str:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), os_key=os_key))
    at.run(timeout=90)
    if at.exception:
        ex = at.exception[0]
        detail = getattr(ex, "value", ex)
        pytest.fail(f"credentials.show() raised {type(detail).__name__}: {detail}")

    chunks: list[str] = []
    for attr in ("markdown", "info", "warning", "success", "error", "caption"):
        for el in getattr(at, attr, []):
            value = getattr(el, "value", None) or getattr(el, "body", None)
            if isinstance(value, str):
                chunks.append(value)
    return "\n".join(chunks)


@pytest.fixture(scope="module")
def rendered() -> dict[str, str]:
    from src.dashboard.utils.os_hints import MAC, WINDOWS
    return {WINDOWS: _render(WINDOWS), MAC: _render(MAC)}


def test_the_page_actually_produced_text(rendered):
    """Everything below is vacuous against an empty render."""
    for os_key, text in rendered.items():
        assert len(text) > 200, (
            f"the credentials page rendered {len(text)} chars for os={os_key} — "
            "too little to assert anything about. Has the view stopped emitting "
            "markdown, or is the AppTest session missing something?"
        )


@pytest.mark.parametrize("os_key", ["windows", "mac"])
def test_no_token_reaches_the_page(rendered, os_key):
    """A token that resolves in a unit test can still be printed raw by a view."""
    leaked = sorted(set(_UNRESOLVED.findall(rendered[os_key])))
    assert not leaked, (
        f"unresolved token(s) on the rendered page for os={os_key}: {leaked}. "
        "The string reached st.markdown without going through resolve_os_tokens "
        "(the view renders guides via `_os_md`)."
    )


def test_the_mac_render_never_spells_a_windows_shortcut(rendered):
    """The Grinch failure, verbatim: a macOS reader told to press Ctrl+U."""
    from src.dashboard.utils.os_hints import MAC

    stray = sorted(set(_WINDOWS_ONLY.findall(rendered[MAC])))
    assert not stray, (
        f"Windows-only shortcut(s) rendered for macOS: {stray}. A macOS artist "
        "pressing these gets nothing — this is the 2026-08-12 beta failure."
    )


def test_the_windows_render_never_spells_a_mac_shortcut(rendered):
    """The symmetric error is just as wrong, and much easier to ship unnoticed."""
    from src.dashboard.utils.os_hints import WINDOWS

    stray = sorted(set(_MAC_ONLY.findall(rendered[WINDOWS])))
    assert not stray, (
        f"macOS-only spelling(s) rendered for Windows: {stray}."
    )


def test_the_two_renders_differ_exactly_when_the_guides_depend_on_the_os(rendered):
    """Le rendu suit le CONTENU, dans les deux sens.

    Cette assertion disait « les deux rendus diffèrent », point. C'était vrai tant
    qu'un guide portait un jeton, et c'est devenu faux le 2026-09-04 quand le dernier
    (`{{COPY}}`, guide Meta) est parti : le champ Ad Account accepte désormais l'URL
    entière, donc plus personne n'a à sélectionner une sous-chaîne au clavier. Le test
    est alors passé au rouge sur du code correct — il affirmait un FAIT de contenu là
    où la question est une RÈGLE.

    La règle, elle, tient dans les deux états : deux rendus identiques sont corrects
    si et seulement si aucun guide ne dépend du clavier — et dans ce cas le sélecteur
    d'OS ne doit pas non plus s'afficher, sans quoi la page offrirait un choix entre
    deux réponses identiques. Le jour où un guide redemande un raccourci, la même
    assertion exige à nouveau que les rendus diffèrent, sans qu'on ait rien à toucher.
    """
    from src.dashboard.content.credential_guides import CREDENTIAL_GUIDES
    from src.dashboard.content.credential_guides_st import _needs_os_selector
    from src.dashboard.utils.os_hints import MAC, WINDOWS

    os_dependent = [g.key for g in CREDENTIAL_GUIDES if _needs_os_selector(g)]
    differ = rendered[WINDOWS] != rendered[MAC]

    if os_dependent:
        assert differ, (
            f"guide(s) {os_dependent} carry a keyboard instruction, yet the Windows "
            "and macOS renders are byte-identical — `_guide_os` is not reaching the "
            "resolver, so every check above proves nothing."
        )
    else:
        assert not differ, (
            "no credential guide depends on the keyboard any more, yet the two "
            "renders differ. Something is branching on the OS outside the token "
            "resolver, where no test can see it."
        )
        assert "Instructions adaptées" not in rendered[WINDOWS], (
            "the OS selector is still drawn while no guide depends on the OS — it "
            "offers a choice between two identical answers, on top of the one field "
            "the artist has to fill (reported 2026-09-04)."
        )
