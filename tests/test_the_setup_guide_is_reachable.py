"""
Guard — l'assistant de mise en route doit être joignable, et les étapes doivent mener.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: src/dashboard/app.py, src/dashboard/views/home.py
Persists in: nothing

Error class: the-page-that-tells-you-what-to-do-is-unreachable.

Mesuré le 2026-08-23 sur les notes de deux tests artistes.

`views/onboarding.py` — celui qui porte la sélection par plateforme et la matrice, et donc
le seul qui dise à un artiste QUOI FAIRE — n'était dans **aucune section de navigation** et
n'était pas une page valide. Il n'était joignable que par `?page=onboarding`, produit à deux
endroits : l'écran post-inscription et l'e-mail de vérification. **Mail fermé, onglet
fermé : la page n'existait plus.** Rien ne le signalait, parce qu'une page injoignable ne
lève pas.

Et sur l'accueil, les quatre étapes de mise en route NOMMAIENT leur destination sans y
mener : `for done, label, _page in steps:` — la clé de page était liée à `_page` puis
jetée, et les lignes étaient du `st.markdown`. Few (*Information Dashboard Design*) : un
tableau de bord sert de rampe de lancement, on clique la donnée elle-même.

Les deux défauts ont la même forme : le produit sait où l'utilisateur doit aller, le dit,
et ne l'y emmène pas.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "src" / "dashboard" / "app.py"
_HOME = _ROOT / "src" / "dashboard" / "views" / "home.py"
_PLANS = _ROOT / "src" / "database" / "stripe_schema.py"


def _nav_keys() -> set[str]:
    """Toutes les clés de page déclarées dans `_NAV_SECTIONS`."""
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.Assign)
                and any(getattr(t, "id", "") == "_NAV_SECTIONS" for t in n.targets))
    return {
        c.value for c in ast.walk(node.value)
        if isinstance(c, ast.Constant) and isinstance(c.value, str)
    }


def test_the_wizard_is_in_the_navigation():
    assert "onboarding" in _nav_keys(), (
        "`onboarding` n'est dans aucune section de navigation. C'est la page qui dit à "
        "l'artiste quoi faire ; sans entrée de menu elle n'est joignable que depuis "
        "l'e-mail de vérification, et disparaît dès qu'il ferme l'onglet."
    )


def test_the_wizard_is_routed():
    text = _APP.read_text(encoding="utf-8")
    assert 'page == "onboarding"' in text, (
        "l'entrée de menu existe mais aucune branche de routage ne la sert : la page "
        "s'afficherait vide."
    )


def test_no_plan_locks_the_wizard():
    """Faire payer le droit de brancher ses propres comptes n'a pas de sens."""
    text = _PLANS.read_text(encoding="utf-8")
    tree = ast.parse(text)
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.Assign)
                and any(getattr(t, "id", "") == "ALWAYS_ACCESSIBLE" for t in n.targets))
    keys = {c.value for c in ast.walk(node.value)
            if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    assert "onboarding" in keys, (
        "`onboarding` doit être dans ALWAYS_ACCESSIBLE : sinon un artiste au plan Free "
        "voit 🔒 sur la page qui lui explique comment se configurer."
    )


def test_a_first_run_lands_on_the_wizard():
    text = _APP.read_text(encoding="utf-8")
    assert "_first_run_landing" in text, (
        "aucun aiguillage de première connexion : tout le monde atterrit sur `home`, "
        "qui pour un artiste neuf est un tableau d'état vide."
    )
    tree = ast.parse(text)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_first_run_landing"), None)
    assert fn is not None
    returns = {c.value for c in ast.walk(fn)
               if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    assert {"home", "onboarding"} <= returns, (
        "l'aiguillage doit pouvoir rendre les DEUX : `onboarding` tant que rien n'est "
        "branché, `home` ensuite — la note dit « et ensuite sur accueil »."
    )


def test_the_home_steps_lead_somewhere():
    """La clé de page ne doit plus être jetée."""
    tree = ast.parse(_HOME.read_text(encoding="utf-8"))
    goto_calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and (getattr(n.func, "id", "") == "goto" or getattr(n.func, "attr", "") == "goto")
    ]
    assert goto_calls, (
        "aucun appel à `goto()` dans home.py : les étapes de mise en route nomment leur "
        "destination sans y mener. C'était `for done, label, _page in steps:` — la clé "
        "liée puis jetée."
    )


def test_the_navigation_rule_lives_in_one_place():
    """Deux copies de la règle de navigation divergeraient — le dépôt a déjà payé ça."""
    nav = _ROOT / "src" / "dashboard" / "utils" / "navigation.py"
    assert nav.is_file(), "le helper de navigation partagé a disparu"
    onboarding = (_ROOT / "src" / "dashboard" / "views" / "onboarding.py").read_text(
        encoding="utf-8")
    assert "from src.dashboard.utils.navigation import goto" in onboarding, (
        "onboarding.py doit déléguer au helper partagé plutôt que reporter sa propre "
        "règle de navigation"
    )
