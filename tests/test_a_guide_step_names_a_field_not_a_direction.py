"""Guard: a guide step points at a field by NAME, never by where it sits.

Type: Utility
Uses: ast, src.dashboard.content.credential_guides
Triggers: pytest
Persists in: nothing

Error class `instruction-points-by-direction-not-by-name`.

Reported 2026-09-06: « c'est à gauche, pas au-dessus ». The Meta step said « colle-la
au-dessus », and the comment defending that wording said the opposite of the comment
it had replaced (« au-dessus » et non « ⬅ »). Both were right, which is the point:
`_render.py` renders `st.columns([3, 2])`, so the form is on the LEFT on a wide
screen and ABOVE once Streamlit stacks the columns on a narrow one. A direction is a
property of the viewport, not of the guide.

And the same text ships as a PDF at sign-up, where neither word designates anything
at all — there is no form on the page.

Four steps carried the defect (spotify, youtube, meta, instagram) in both languages,
which is why this reads the catalogue rather than a list of keys: the fifth to be
written is covered by construction.

A direction is still ALLOWED as a hint — « à gauche » helps on the screen where it is
true. What is forbidden is a direction used INSTEAD of the field's name.
"""
from __future__ import annotations

import pytest

from src.dashboard.content.credential_guides import CREDENTIAL_GUIDES
from src.dashboard.content.credential_guides_en import CREDENTIAL_GUIDES_EN

# Les mots qui désignent une position. Une étape qui en emploie un DOIT aussi nommer
# le champ visé ; l'inverse (nommer le champ sans direction) est parfait.
_DIRECTIONS_FR = ("au-dessus", "au dessus", "ci-dessus", "en dessous", "plus haut",
                  "plus bas")
_DIRECTIONS_EN = ("above", "below", "underneath", "further up", "further down")

_CATALOGUES = [("fr", CREDENTIAL_GUIDES, _DIRECTIONS_FR),
               ("en", CREDENTIAL_GUIDES_EN, _DIRECTIONS_EN)]


def _paste_steps(guide):
    """Les étapes qui demandent de COLLER quelque chose — celles qui visent un champ."""
    verbs = ("colle", "coller", "paste", "saisis", "enter ")
    return [str(s.text) for s in guide.steps
            if any(v in str(s.text).lower() for v in verbs)]


def test_the_sweep_sees_the_steps_it_is_about():
    """Sinon toutes les assertions ci-dessous sont vraies de rien."""
    total = sum(len(_paste_steps(g)) for _, cat, _ in _CATALOGUES for g in cat)
    assert total >= 8, (
        f"seulement {total} étape(s) de collage trouvée(s) : le balayage ne voit "
        "plus ce qu'il garde (il y en avait 8 le 2026-09-06, 4 par langue)")


@pytest.mark.parametrize("lang,catalogue,directions", _CATALOGUES)
def test_a_step_that_says_where_also_says_what(lang, catalogue, directions):
    """Une direction sans nom de champ ne survit ni au viewport, ni au PDF."""
    offenders = []
    for guide in catalogue:
        names = [f.label for f in guide.fields]
        for text in _paste_steps(guide):
            used = [d for d in directions if d in text.lower()]
            if not used:
                continue
            if not any(name in text for name in names):
                offenders.append(
                    f"{lang}/{guide.key} : {used} sans nommer un champ "
                    f"({names}) — {text[:80]}")
    assert not offenders, (
        "ces étapes désignent un champ par sa position seule :\n  "
        + "\n  ".join(offenders)
        + "\n\nLa mise en page est `st.columns([3, 2])` : le formulaire est à GAUCHE "
          "sur un écran large et AU-DESSUS sur un écran étroit, et ce texte part "
          "aussi en PDF, où il n'y a aucun formulaire. Nomme le champ.")


@pytest.mark.parametrize("lang,catalogue,_d", _CATALOGUES)
def test_every_named_field_in_a_step_exists_on_that_guide(lang, catalogue, _d):
    """Nommer un champ ne vaut que si le nom est celui que l'artiste lit.

    Sans ceci, la correction ci-dessus s'achète en inventant un libellé — et une
    étape qui nomme un champ inexistant est pire qu'une direction périmée.
    """
    checked = 0
    for guide in catalogue:
        names = [f.label for f in guide.fields]
        for text in _paste_steps(guide):
            for name in names:
                if name in text:
                    checked += 1
    assert checked >= 4, (
        f"{lang} : seulement {checked} étape(s) nomment un champ existant — les "
        "autres désignent le vide ou une position")
