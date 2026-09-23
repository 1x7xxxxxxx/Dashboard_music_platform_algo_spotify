"""Garde : « Se connecter avec Google » vit DANS le cadre, à côté de « Se connecter ».

Type: Utility
Uses: streamlit.testing.v1.AppTest, src.dashboard.auth
Triggers: pytest
Persists in: nothing

Demandé le 2026-09-23 par le propriétaire, après son premier aller-retour Google réussi
en production : le bouton « juste à côté de connexion, avec un fond flashi, qu'on
puisse cliquer facilement dessus, intégré dans le cadre ». Il vivait SOUS le
formulaire, en bouton gris pleine largeur, entre le formulaire et le lien
d'inscription.

Ce que ce garde couvre, par un RENDU réel et non une lecture du source :
* avec Google configuré, les deux boutons sont dans le formulaire, sur la même ligne ;
* « Se connecter » est le PREMIER bouton de soumission — Streamlit assimile la touche
  Entrée au premier : un mot de passe validé au clavier ne doit jamais partir chez
  Google ;
* le style vif est posé, et ses deux teintes gardent un contraste AA avec le blanc ;
* sans configuration, Google disparaît et « Se connecter » reste seul.
Ce qu'il NE couvre PAS : l'apparence dans un vrai navigateur (le sélecteur
`.st-key-<key>` dépend de la version de Streamlit, épinglée à 1.63.0), ni l'aller-retour
chez Google, prouvé à la main en production le 2026-09-23.
"""
from __future__ import annotations

import re

from streamlit.testing.v1 import AppTest


def _script(configured: bool) -> str:
    return f'''
import streamlit as st
from src.dashboard import auth
from src.dashboard.utils import google_auth
_real_configure = google_auth.configure
google_auth.configure = lambda: {configured}
try:
    with st.form("login"):
        st.text_input("user", key="u")
        submitted = auth._boutons_de_connexion()
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


def test_both_buttons_share_the_form_and_sign_in_comes_first() -> None:
    at = _run(configured=True)
    keys = [b.key for b in at.button]
    assert keys[:2] == ["login_submit", "google_signin"], (
        f"ordre des boutons de soumission : {keys}. « Se connecter » doit être le "
        "PREMIER — la touche Entrée soumet par lui.")
    assert len(at.columns) >= 2, "les deux boutons ne sont pas sur la même ligne"


def test_enter_or_click_on_sign_in_submits_the_password_path() -> None:
    at = _run(configured=True)
    at.button(key="login_submit").click().run()
    assert any("SUBMITTED" in m.value for m in at.markdown), "le mot de passe n'a pas été soumis"


def test_the_google_button_is_styled_loud_and_still_readable() -> None:
    from src.dashboard.auth import _GOOGLE_BUTTON_CSS

    at = _run(configured=True)
    css = [m.value for m in at.markdown if "st-key-google_signin" in m.value]
    assert css, "le style du bouton Google n'est pas posé"

    def contrast_on_white(hexa: str) -> float:
        rgb = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
        return 1.05 / (lum + 0.05)

    stops = re.findall(r"linear-gradient\([^)]*\)", _GOOGLE_BUTTON_CSS)[0]
    colours = re.findall(r"#[0-9A-Fa-f]{6}", stops)
    assert len(colours) >= 2, f"non-vacuité : dégradé illisible ({stops})"
    faibles = {c: round(contrast_on_white(c), 2) for c in colours if contrast_on_white(c) < 4.5}
    assert not faibles, f"texte blanc sous le seuil AA 4.5:1 sur {faibles}"


def test_without_google_configured_sign_in_stands_alone() -> None:
    at = _run(configured=False)
    assert [b.key for b in at.button] == ["login_submit"]
    assert not any("st-key-google_signin" in m.value for m in at.markdown)
