"""Le diagnostic d'onboarding lit la table de ROUTAGE, jamais le nom de la page.

Type: Test
Uses: tools/artist_first_look.py, src/dashboard/app.py
Triggers: CI, `python3 .claude/scripts/select_tests.py`
Depends on: rien (aucune base, aucun réseau)

Le défaut gardé
---------------
Mesuré le 2026-09-12 par `make artist-firstlook-prod ARTIST=1` : le rapport annonçait
**2 pages sur 6 en ERREUR** — `process_guide` (`ModuleNotFoundError`) et `upload_csv`
(`ImportError: cannot import name 'show'`). Les deux pages fonctionnent. `app.py` les
route ailleurs depuis la fusion du 2026-09-04 (`upload_csv` → `views.credentials`,
`process_guide` → `views.onboarding_health`) ; l'outil importait le module portant le
NOM de la page.

Classe `a-diagnostic-that-reads-a-name-not-a-route`. Un diagnostic qui crie sur deux
pages saines apprend à lire ses ❌ en diagonale — et le jour où l'un est vrai, il passe
avec les autres. Le dépôt a déjà payé cette forme sur le garde `/kpis`, dont les
28 assertions « pas de 500 » étaient toutes satisfaites par des 401.

Ce que ce fichier vérifie, et ce qu'il ne peut pas vérifier
----------------------------------------------------------
Il vérifie que CHAQUE page du parcours est atteignable par une branche d'`app.py`, et
que le module résolu existe et expose `show`. Il ne rend AUCUN verdict sur ce que la
page affiche — c'est le travail de l'outil lui-même, qui a besoin d'une base.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        "artist_first_look", ROOT / "tools" / "artist_first_look.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_journey_page_is_routed_by_app_py():
    """Une page du parcours qu'aucune branche ne route est INATTEIGNABLE."""
    tool = _tool()
    unrouted = []
    for view, _why in tool.JOURNEY:
        try:
            tool._module_of(view)
        except KeyError:
            unrouted.append(view)
    assert not unrouted, (
        f"pages du parcours qu'aucune branche de `_render_page` ne route : {unrouted}. "
        f"Soit le produit a une page inatteignable, soit `JOURNEY` nomme une clé morte."
    )


def test_each_routed_module_exists_and_exposes_show():
    """Résoudre une route ne suffit pas : le module doit exister et servir la page."""
    tool = _tool()
    broken = []
    for view, _why in tool.JOURNEY:
        module = tool._module_of(view)
        rel = pathlib.Path(*module.split("."))
        for candidate in (ROOT / f"{rel}.py", ROOT / rel / "__init__.py"):
            if candidate.exists():
                tree = ast.parse(candidate.read_text(encoding="utf-8"))
                names = {n.name for n in tree.body
                         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                names |= {a.asname or a.name
                          for n in tree.body if isinstance(n, ast.ImportFrom)
                          for a in n.names}
                if "show" not in names:
                    broken.append(f"{view} → {module} (aucun `show`)")
                break
        else:
            broken.append(f"{view} → {module} (fichier absent)")
    assert not broken, f"routes cassées : {broken}"


def test_the_two_measured_pages_resolve_away_from_their_own_name():
    """Le défaut d'origine, nommé : ces deux pages ne sont PAS servies par leur nom.

    Si `app.py` rend un jour `views.upload_csv` à nouveau, cette assertion tombe — et
    c'est voulu : elle documente alors une régression de la fusion, pas de l'outil.
    """
    tool = _tool()
    assert tool._module_of("upload_csv") == "src.dashboard.views.credentials"
    assert tool._module_of("process_guide") == "src.dashboard.views.onboarding_health"


# --- non-vacuité : le garde doit pouvoir rougir ---------------------------------

def test_an_unrouted_page_raises_rather_than_importing_by_name():
    """Sans cette levée, l'outil retomberait sur l'import par nom — le défaut même."""
    tool = _tool()
    with pytest.raises(KeyError):
        tool._module_of("une_page_qui_n_existe_pas_du_tout")


def test_the_resolver_parses_and_does_not_grep():
    """Une route citée dans un COMMENTAIRE n'est pas une route.

    Le premier garde de `a-verification-read-through-a-filtering-wrapper` a été refusé
    le jour de son écriture pour avoir cherché une chaîne ; celui-ci passe par `ast`,
    et ce test le prouve en lui donnant un `app.py` où la seule mention est du texte.
    """
    tool = _tool()
    fake = (
        "def _render_page(page):\n"
        "    # elif page == \"fantome\": from views.fantome import show; show()\n"
        "    '''from views.docstring_only import show'''\n"
        "    if page == \"vraie\":\n"
        "        from views.vraie import show; show()\n"
    )
    tree = ast.parse(fake)
    dispatch = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "_render_page")
    routes = {}
    for node in ast.walk(dispatch):
        if not isinstance(node, ast.If):
            continue
        for key in tool._compared_keys(node.test):
            mods = [s.module for stmt in node.body for s in ast.walk(stmt)
                    if isinstance(s, ast.ImportFrom) and s.module
                    and any(a.name == "show" for a in s.names)]
            if mods:
                routes[key] = mods[0]
    assert routes == {"vraie": "views.vraie"}, (
        f"le résolveur a ramassé une mention textuelle : {routes}")


def test_an_elif_branch_does_not_inherit_the_previous_import():
    """`ast.walk(node)` descend dans `orelse` : toute la chaîne hériterait du premier.

    C'est l'erreur exacte que `node.body` évite. Sans elle, `home` et les 41 autres
    pages résoudraient toutes vers `views.home`, et l'outil rendrait vert partout.
    """
    tool = _tool()
    routes = tool._route_map()
    distinct = set(routes.values())
    assert len(distinct) > 30, (
        f"{len(routes)} pages routées mais seulement {len(distinct)} modules distincts "
        f"— une branche hérite de l'import d'une autre")
    assert routes["home"] == "views.home"
    assert routes["account"] == "views.account"
