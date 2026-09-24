"""Garde : « Se connecter avec Google » vit sur la ligne du titre « Connexion ».

Type: Utility
Uses: streamlit.testing.v1.AppTest, src.dashboard.auth
Triggers: pytest
Persists in: nothing

Demandé le 2026-09-23 par le propriétaire, en trois temps : le bouton dans le cadre,
à côté du bouton de connexion ; puis le bouton standard de Google, logo « G » compris ;
puis « juste à côté du bouton "Connexion" et non "Se connecter", qu'on laisse après
les champs de saisie ».

Le piège que ce garde tient fermé : Streamlit valide un formulaire par la touche
Entrée en déclenchant `submitButtons[0]`, le premier bouton de soumission AFFICHÉ
(lu dans le JS de la v1.63.0, `allowFormEnterToSubmit` / `submitForm`). Un bouton
Google posé au-dessus des champs COMME bouton de soumission aurait volé la touche
Entrée. Il est donc un `st.button` ordinaire, HORS du formulaire.

Ce que ce garde couvre, par un RENDU réel de `_cadre_de_connexion()` :
* le bouton Google partage la rangée horizontale du titre « Connexion » ;
* il n'est PAS dans le formulaire, qui n'a qu'un bouton de soumission : « Se connecter » ;
* les deux boutons ont la même largeur fixe (courts, jamais tronqués) ;
* « Se connecter » est aligné à GAUCHE, sur le bord des champs (demandé le
  2026-09-24 : centré, il flottait seul au milieu du cadre) ;
* le style est celui du bouton de Google — blanc, texte sombre lisible (AA), « G »
  quatre couleurs ;
* sans configuration, Google disparaît et « Se connecter » reste seul.
Ce qu'il NE couvre PAS : l'apparence dans un vrai navigateur (le sélecteur
`.st-key-<key>` dépend de la version de Streamlit, épinglée à 1.63.0), ni l'aller-retour
chez Google, prouvé à la main en production le 2026-09-23.
"""
from __future__ import annotations

import ast
import inspect
import re
import urllib.parse

from streamlit.testing.v1 import AppTest


def _script(configured: bool) -> str:
    return f'''
import streamlit as st
from src.dashboard import auth
from src.dashboard.utils import google_auth
_real_configure = google_auth.configure
google_auth.configure = lambda: {configured}
try:
    _u, _p, submitted = auth._cadre_de_connexion()
    st.write("SUBMITTED" if submitted else "IDLE")
finally:
    # AppTest runs in THIS process: a double left in place leaks into every test after.
    google_auth.configure = _real_configure
'''


def _run(configured: bool) -> AppTest:
    at = AppTest.from_string(_script(configured), default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def _walk(node):
    yield node
    for child in (getattr(node, "children", None) or {}).values():
        yield from _walk(child)


def _keys_under(node) -> set:
    return {getattr(n, "key", None) for n in _walk(node)} - {None}


def test_google_shares_the_row_of_the_connexion_title() -> None:
    at = _run(configured=True)
    rows = [n for n in _walk(at._tree) if getattr(n, "type", "") == "flex_container"
            and "google_signin" in {getattr(c, "key", None)
                                    for c in (n.children or {}).values()}]
    assert rows, "le bouton Google n'est dans aucune rangée"
    row = list(rows[0].children.values())
    assert [getattr(c, "type", "") for c in row] == ["subheader", "button"], (
        f"la rangée porte {[getattr(c, 'type', '') for c in row]} : attendu le titre puis "
        "le bouton Google, et rien entre les deux (un <style> y prendrait une place)")
    assert "Connexion" in row[0].value, "le bouton Google n'est pas sur la ligne du titre"


def test_the_form_has_one_submit_button_and_it_is_sign_in() -> None:
    """Entrée soumet par `submitButtons[0]` : il ne doit y en avoir qu'un, le bon."""
    at = _run(configured=True)
    forms = [n for n in _walk(at._tree) if getattr(n, "type", "") == "form"]
    assert len(forms) == 1, f"non-vacuité : {len(forms)} formulaire(s)"
    submitters = [b.key for b in at.button if b.proto.is_form_submitter]
    assert submitters == ["login_submit"], (
        f"boutons de soumission : {submitters}. Google en bouton de soumission volerait "
        "la touche Entrée à un mot de passe validé au clavier.")
    assert "google_signin" not in _keys_under(forms[0]), "Google est DANS le formulaire"
    assert "login_submit" in _keys_under(forms[0])


def test_sign_in_still_submits_the_password_path() -> None:
    at = _run(configured=True)
    at.button(key="login_submit").click().run()
    assert any("SUBMITTED" in m.value for m in at.markdown), "le mot de passe n'a pas été soumis"


def test_both_buttons_are_short_and_equal() -> None:
    """Une largeur FIXE, pas un pourcentage : à 25 % du cadre, le libellé Google
    était tronqué à 1 024 px (« Se connecter avec G… »)."""
    from src.dashboard import auth
    from src.dashboard.auth import _BUTTON_WIDTH_PX

    for fn, verb in ((auth._bouton_google, "button"),
                     (auth._bouton_se_connecter, "form_submit_button")):
        calls = [c for c in ast.walk(ast.parse(inspect.getsource(fn)))
                 if isinstance(c, ast.Call) and getattr(c.func, "attr", "") == verb]
        assert calls, f"non-vacuité : aucun `{verb}` dans {fn.__name__}"
        widths = [kw.value for c in calls for kw in c.keywords if kw.arg == "width"]
        assert widths and all(isinstance(w, ast.Name) and w.id == "_BUTTON_WIDTH_PX"
                              for w in widths), (
            f"{fn.__name__} : le bouton doit porter `width=_BUTTON_WIDTH_PX`")
    assert 220 <= _BUTTON_WIDTH_PX <= 320, (
        f"{_BUTTON_WIDTH_PX} px : sous 220 le libellé Google se tronque, au-dessus de "
        "320 les boutons redeviennent longs.")


def test_sign_in_is_aligned_on_the_fields_left_edge() -> None:
    """Centré, « Se connecter » flottait seul au milieu d'un cadre dont le titre, les
    libellés, les champs et le lien d'inscription partent tous du bord gauche."""
    at = _run(configured=True)
    rows = [n for n in _walk(at._tree) if getattr(n, "type", "") == "flex_container"
            and "login_submit" in {getattr(c, "key", None)
                                   for c in (n.children or {}).values()}]
    assert rows, "non-vacuité : « Se connecter » n'est dans aucune rangée"
    justify = rows[0].proto.flex_container.justify
    assert justify == type(rows[0].proto.flex_container).Justify.JUSTIFY_START, (
        f"« Se connecter » est justifié {justify} : attendu JUSTIFY_START, le bord "
        "gauche des champs")


def test_the_google_button_looks_like_googles_own() -> None:
    """Fond blanc, bordure grise, texte sombre, « G » quatre couleurs — comme partout."""
    from src.dashboard.auth import _GOOGLE_BUTTON_CSS, _GOOGLE_G_LOGO

    at = _run(configured=True)
    assert any("st-key-google_signin" in m.value for m in at.markdown), "style non posé"

    def luminance(hexa: str) -> float:
        rgb = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    fond = re.search(r"background:\s*(#[0-9A-Fa-f]{6})", _GOOGLE_BUTTON_CSS).group(1)
    texte = re.search(r"\bcolor:\s*(#[0-9A-Fa-f]{6})", _GOOGLE_BUTTON_CSS).group(1)
    assert fond.upper() == "#FFFFFF", f"fond {fond} : le bouton standard de Google est blanc"
    ratio = (luminance(fond) + 0.05) / (luminance(texte) + 0.05)
    assert ratio >= 4.5, f"texte {texte} sur {fond} : {ratio:.2f}:1, sous le seuil AA"

    logo = urllib.parse.unquote(_GOOGLE_G_LOGO)
    assert logo.startswith("data:image/svg+xml,<svg"), "le logo n'est pas un SVG embarqué"
    manquantes = [c for c in ("#EA4335", "#4285F4", "#FBBC05", "#34A853") if c not in logo]
    assert not manquantes, f"le « G » de Google a perdu ses couleurs {manquantes}"
    assert 'url("data:image/svg+xml,' in _GOOGLE_BUTTON_CSS, "le logo n'est pas branché"


def test_without_google_configured_sign_in_stands_alone() -> None:
    at = _run(configured=False)
    assert [b.key for b in at.button] == ["login_submit"]
    assert not any("st-key-google_signin" in m.value for m in at.markdown)
