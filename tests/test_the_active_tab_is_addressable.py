"""L'onglet actif est un état de l'URL, pas une propriété invisible du rendu.

Type: Test
Uses: credentials.router (AST + fonctions pures)
Depends on: src/dashboard/views/credentials/router.py
Persists in: nothing

La question posée, et la réponse
---------------------------------
« On n'a pas un refactor avec la meilleure logique possible pour les onglets, la
redirection, etc. ? » (2026-09-05). Oui — et les trois bugs signalés le même jour
étaient les symptômes d'un seul défaut de conception, pas des accidents séparés.

`st.tabs` rend TOUS ses panneaux et n'expose AUCUN contrôle de l'onglet actif. Chaque
fois qu'il a fallu « ouvrir l'onglet X », on l'a obtenu en RÉORDONNANT la liste :

  * la barre bougeait sous l'artiste entre deux reruns — « ça nous ramène sur Spotify
    au lieu de Meta » : l'ordre était réordonné au rerun d'un enregistrement, puis
    revenait à sa place au suivant ;
  * « quel onglet montre le verdict » se découplait de « quel onglet est ouvert »,
    d'où une rustine `verdict_owner` — qui a fini par masquer le verdict entièrement,
    le routeur ayant cessé de la passer sans que rien ne le dise ;
  * rien n'était adressable : ni lien profond, ni bouton Précédent.

L'onglet devient donc un état comme la page : `?page=credentials&tab=soundcloud`, une
barre qui est un vrai widget pilotable, un seul panneau rendu. Rediriger n'est plus
qu'écrire l'état.

Ce que ce fichier fige : la RÈGLE, pas la séquence de clics — un test qui rejoue six
écrans casse au premier changement de libellé et ne dit plus rien.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.views.credentials.router import (
    _TAB_PARAM, _TAB_STATE, _resolve_active_tab,
)

_ROOT = Path(__file__).resolve().parents[1]
_ROUTER = _ROOT / "src" / "dashboard" / "views" / "credentials" / "router.py"


def _show() -> ast.FunctionDef:
    tree = ast.parse(_ROUTER.read_text(encoding="utf-8"))
    return next(f for f in ast.walk(tree)
                if isinstance(f, ast.FunctionDef) and f.name == "show")


# ── La résolution : session, puis URL, puis défaut ───────────────────────────

def test_a_fresh_arrival_opens_the_first_tab():
    assert _resolve_active_tab(["spotify", "soundcloud"]) in ("spotify", "soundcloud")


def test_an_unknown_tab_falls_back_instead_of_rendering_nothing(monkeypatch):
    """Un onglet renommé, un lien ancien : on ouvre le premier, pas une page vide."""
    import streamlit as st

    monkeypatch.setitem(st.session_state, _TAB_STATE, "plateforme-disparue")
    assert _resolve_active_tab(["spotify", "soundcloud"]) == "spotify"


def test_the_session_wins_over_the_url(monkeypatch):
    """L'ORDRE compte, et c'est le même défaut qu'un niveau plus haut.

    La session porte ce que l'artiste vient de choisir ou ce qu'une redirection vient
    d'écrire ; l'URL porte ce qu'il a collé ou mis en signet. Lire l'URL en premier
    ferait gagner un paramètre PÉRIMÉ sur un clic frais — exactement le défaut corrigé
    sur la PAGE le 2026-09-04 (`?page=credentials` hérité battait l'atterrissage).
    """
    import streamlit as st

    monkeypatch.setitem(st.session_state, _TAB_STATE, "soundcloud")
    st.query_params[_TAB_PARAM] = "spotify"
    try:
        assert _resolve_active_tab(["spotify", "soundcloud"]) == "soundcloud"
    finally:
        st.query_params.pop(_TAB_PARAM, None)


# ── La structure : un état, un panneau, aucun réordonnancement ───────────────

def test_the_tab_bar_is_a_controllable_widget():
    """`st.tabs` n'expose pas son onglet actif — c'est toute la raison du refactor."""
    fn = _show()
    tabs = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", "") == "tabs"]
    assert not tabs, (
        "`st.tabs` est revenu : il ne permet pas de choisir l'onglet ouvert, donc "
        "toute redirection repasserait par un réordonnancement — et la barre "
        "rebougerait sous l'artiste entre deux reruns")

    bar = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
           and getattr(n.func, "attr", "") in ("segmented_control", "pills", "radio")]
    assert bar, "il n'y a plus de barre d'onglets du tout"
    keyed = [n for n in bar
             if any(k.arg == "key" and getattr(k.value, "id", "") == "_TAB_STATE"
                    for k in n.keywords)]
    assert keyed, (
        "la barre n'est pas pilotable : sans `key=_TAB_STATE`, on ne peut pas lui "
        "imposer un onglet, et rediriger redevient un réordonnancement")


def test_the_url_carries_the_active_tab():
    fn = _show()
    writes = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Subscript)
                      and "query_params" in ast.dump(t.value) for t in n.targets)]
    assert writes, (
        "l'onglet actif n'est plus écrit dans l'URL : plus de lien profond, plus de "
        "bouton Précédent, et un rechargement rouvre le premier onglet")


def test_only_the_active_panel_is_rendered():
    """Un seul panneau — c'est ce qui rend la rustine `verdict_owner` inutile.

    Elle existait parce que `st.tabs` rendait les cinq et que `pop` faisait
    disparaître le verdict dans le premier venu. Elle a d'ailleurs survécu une heure
    de trop : le routeur avait cessé de la passer, sa valeur par défaut ne valait
    jamais la plateforme, et le verdict ne s'affichait plus DU TOUT.
    """
    fn = _show()
    renders = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
               and getattr(n.func, "id", "") == "_render_platform_tab"]
    assert len(renders) == 1, (
        f"{len(renders)} appels de panneau : un seul doit être rendu, celui qui est "
        "actif")
    assert not any(k.arg == "verdict_owner" for c in renders for k in c.keywords), (
        "`verdict_owner` est revenu : il n'a de sens que si plusieurs panneaux sont "
        "rendus, ce qui n'est plus le cas")


def test_nothing_reorders_the_tabs_any_more():
    fn = _show()
    reorders = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
                and any(getattr(t, "id", "") == "ordered" for t in n.targets)]
    assert len(reorders) == 1, (
        f"{len(reorders)} affectations de `ordered` : le réordonnancement est revenu, "
        "et avec lui la barre qui bouge entre deux reruns")


def test_a_redirect_writes_the_state_before_the_widget_exists():
    """Poser la clé APRÈS l'instanciation n'a aucun effet — Streamlit refuse.

    C'est la seule contrainte technique de ce mécanisme, et le dépôt l'a déjà payée
    pour le menu (`_select_nav_radio` : « légal parce que ceci tourne AVANT que les
    radios soient instanciées »).
    """
    src = ast.get_source_segment(_ROUTER.read_text(encoding="utf-8"), _show()) or ""
    tree = ast.parse(src)
    body = list(ast.walk(tree))

    def _line(pred) -> int | None:
        hits = [n.lineno for n in body if pred(n)]
        return min(hits) if hits else None

    set_state = _line(lambda n: isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Subscript)
                              and getattr(t.slice, "id", "") == "_TAB_STATE"
                              for t in n.targets))
    widget = _line(lambda n: isinstance(n, ast.Call)
                   and getattr(n.func, "attr", "") == "segmented_control")
    assert set_state is not None, "plus rien n'impose d'onglet : la redirection est morte"
    assert widget is not None, "la barre d'onglets a disparu"
    assert set_state < widget, (
        "l'onglet est imposé APRÈS l'instanciation de la barre : Streamlit ignore "
        "l'écriture, et la redirection ne fait rien")


# ── Ce qui a été retiré de l'écran ──────────────────────────────────────────

@pytest.mark.parametrize("key", [
    "credentials.no_creds_banner",       # « Aucun credential configuré… »
    "credentials.no_creds_platform",     # « Aucun credential enregistré… »
])
def test_the_page_no_longer_announces_what_is_missing(key):
    """Un formulaire vide dit déjà qu'il est vide.

    « Aucun credential enregistré pour cette plateforme » était la PREMIÈRE ligne de
    la page pour un artiste qui vient s'inscrire : elle lui annonçait l'absence de ce
    qu'il vient faire, avant de lui montrer où le faire. L'état vit sur « 📋 État de
    tes plateformes », où il se lit pour les six sources d'un coup.
    """
    from src.dashboard.utils.i18n_catalog.credentials import EN

    src = _ROUTER.read_text(encoding="utf-8")
    render = (_ROOT / "src/dashboard/views/credentials/_render.py").read_text(encoding="utf-8")
    for path, text in (("router.py", src), ("_render.py", render)):
        used = [n.value for n in ast.walk(ast.parse(text))
                if isinstance(n, ast.Constant) and n.value == key]
        assert not used, f"{path} annonce de nouveau « {key} »"
    assert key not in EN, f"la traduction de « {key} » survit à son appelant"
