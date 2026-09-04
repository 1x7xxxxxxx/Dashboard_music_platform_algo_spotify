"""Un compte non configuré atterrit sur ses étapes — quelle que soit l'URL.

Type: Test
Uses: app._SETUP_PAGES, app._NAV_SECTIONS, setup_completion (pur)
Depends on: src/dashboard/app.py
Persists in: nothing

Le défaut, reproduit au navigateur le 2026-09-04
------------------------------------------------
« Pourquoi dès que je m'inscris après reset et que j'ai le mail, ça ne nous emmène pas
direct sur les steps de configuration et on arrive direct sur l'app ? Il faudrait le
même parcours tout le temps. »

Le parcours mesuré, pas supposé :

  1. l'artiste entre dans l'application ; le miroir d'URL écrit `?page=home` ;
  2. il se déconnecte — l'écran de connexion garde `?page=home` dans son adresse ;
  3. il se reconnecte. `session_state.clear()` a effacé `_page_mirrored`, donc la
     garde « c'est nous qui avons écrit ce paramètre » ne s'applique plus : le bloc
     d'URL pose `_nav_page = 'home'` ;
  4. `resolve_nav_page` trouve une page valide en session et n'a plus rien à
     décider. L'artiste entre dans l'app avec une configuration à **0/4**, sans
     jamais voir ses étapes.

Deux mécanismes justes qui se contredisaient. Le miroir existe pour qu'un rechargement
retrouve sa page ; l'atterrissage, pour qu'un compte non configuré voie sa mise en
route. Le second gagne : une page retrouvée n'a de valeur que pour quelqu'un qui sait
déjà où il va.

Ce que ce fichier fige
----------------------
La RÈGLE d'arbitrage, pas la séquence de clics — un test de navigation qui rejoue six
écrans casse au premier changement de libellé et ne dit plus rien. Ici : quelles pages
peuvent survivre à une première arrivée, et lesquelles doivent lui céder.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.app import _NAV_SECTIONS, _SETUP_PAGES

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "src" / "dashboard" / "app.py"


def _nav_keys() -> set[str]:
    return {key for _s, _h, items in _NAV_SECTIONS for _l, key in items}


# ── La règle d'arbitrage ─────────────────────────────────────────────────────

def test_the_setup_pages_are_the_ones_a_first_arrival_may_keep():
    """`_SETUP_PAGES` doit contenir l'assistant — sinon le lien du mail se casse.

    Le mot de bienvenue envoie sur `?page=onboarding`. Si l'assistant sortait de cet
    ensemble, l'arbitrage l'écraserait… par lui-même, et le lien tomberait sur une
    boucle. C'est la moitié du garde qu'on oublie en écrivant l'autre.
    """
    assert "onboarding" in _SETUP_PAGES, (
        "l'assistant n'est plus une page de mise en route : le lien `?page=onboarding` "
        "du mot de bienvenue serait écrasé par l'atterrissage"
    )
    assert "credentials" in _SETUP_PAGES, (
        "la page de saisie n'est plus une page de mise en route : un lien profond "
        "vers Credentials pendant l'installation serait détourné"
    )
    assert "home" not in _SETUP_PAGES, (
        "l'accueil est devenu une page de mise en route — c'est précisément la page "
        "qui détournait l'atterrissage (`?page=home` hérité de la session précédente)"
    )


def test_every_setup_page_is_a_real_menu_entry():
    """Non-vacuité : un ensemble de pages fantômes n'arbitrerait rien."""
    unknown = sorted(_SETUP_PAGES - _nav_keys())
    assert not unknown, (
        f"`_SETUP_PAGES` nomme des pages absentes du menu : {unknown}. Elles ne "
        "seraient jamais comparées au paramètre d'URL, donc l'arbitrage serait muet "
        "pour elles."
    )


# ── L'ordre des opérations, qui EST le défaut ───────────────────────────────

def _main_body_src() -> str:
    src = _APP.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "_main_body")
    return ast.get_source_segment(src, fn) or ""


def test_the_first_run_decision_is_taken_before_the_url_is_honoured():
    """`arm_first_run_once` AVANT le bloc d'URL, sinon l'arbitrage n'a rien à lire.

    C'est tout le correctif. Elle n'était appelée que dans `resolve_nav_page`, qui
    tourne APRÈS — au moment où `_nav_page` porte déjà la page héritée de l'URL et
    où il n'y a plus rien à décider.
    """
    body = _main_body_src()
    i_arm = body.find("arm_first_run_once(")
    i_url = body.find("if _page_param:")
    assert i_arm != -1, "`arm_first_run_once` n'est plus appelée dans `_main_body`"
    assert i_url != -1, "le bloc qui honore `?page=` a disparu"
    assert i_arm < i_url, (
        "`arm_first_run_once` est appelée APRÈS le bloc d'URL : au moment où "
        "l'arbitrage se joue, personne n'a encore décidé si cette arrivée est une "
        "première connexion. C'est l'ordre exact qui produisait le défaut."
    )


def test_the_url_block_consults_the_first_run_flag():
    """Le bloc d'URL doit lire le drapeau — pas seulement `_page_mirrored`.

    `_page_mirrored` répond à « est-ce nous qui avons écrit ce paramètre ? ». Après
    `session_state.clear()` la réponse est non, ce qui est vrai et sans rapport avec
    la question qui compte ici : « cet artiste a-t-il fini sa configuration ? »
    """
    body = _main_body_src()
    i_url = body.find("if _page_param:")
    block = body[i_url:i_url + 1400]
    assert "FIRST_RUN_FOCUS" in block, (
        "le bloc d'URL ne consulte pas le drapeau de première arrivée : un "
        "`?page=home` hérité de la session précédente reprendrait la main"
    )
    assert "_SETUP_PAGES" in block, (
        "le bloc d'URL n'exempte pas les pages du parcours : le lien "
        "`?page=onboarding` du mot de bienvenue serait écrasé lui aussi"
    )


# ── La décision elle-même, sur des états lisibles ───────────────────────────

@pytest.mark.parametrize("page,first_run,honoured", [
    ("home",        True,  False),   # le défaut signalé
    ("credentials", True,  True),    # lien profond pendant l'installation
    ("onboarding",  True,  True),    # le lien du mot de bienvenue
    ("home",        False, True),    # configuration finie : l'URL reprend ses droits
    ("youtube",     False, True),
    ("youtube",     True,  False),
])
def test_which_pages_survive_a_first_arrival(page, first_run, honoured):
    """La règle, énoncée une fois, vérifiée sur les six cas qui comptent.

    Elle est recopiée ici volontairement plutôt qu'importée : ce test répond à
    « la règle est-elle celle qu'on veut ? », pas à « le code fait-il ce que le code
    fait ». Un import de la vraie fonction rendrait les six lignes tautologiques.
    """
    detourned = first_run and page not in _SETUP_PAGES
    assert (not detourned) is honoured, (
        f"page={page!r}, première arrivée={first_run} : le paramètre d'URL devrait "
        f"{'être honoré' if honoured else 'céder à la mise en route'}"
    )
