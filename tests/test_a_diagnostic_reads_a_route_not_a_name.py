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


def test_the_resolver_reads_the_table_app_py_dispatches_through():
    """R261 — the tool and app.py read ONE table; there is no chain left to mis-parse.

    Until 2026-09-27 the tool parsed app.py's `elif` chain, and this test proved it
    ignored a route quoted in a comment. The chain is gone: the proof is now identity.
    """
    from src.dashboard.routes import ROUTES
    assert _tool()._route_map() == ROUTES
    tree = ast.parse((ROOT / "src" / "dashboard" / "app.py").read_text(encoding="utf-8"))
    dispatch = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == "get"
                and getattr(n.func.value, "id", "") == "ROUTES"]
    assert dispatch, "app.py no longer dispatches through ROUTES"


def test_the_routes_are_distinct_not_vacuous():
    """Each page resolves to its OWN module — the chain once made all 43 read `views.home`."""
    tool = _tool()
    routes = tool._route_map()
    distinct = set(routes.values())
    assert len(distinct) > 30, (
        f"{len(routes)} pages routées mais seulement {len(distinct)} modules distincts "
        f"— une branche hérite de l'import d'une autre")
    assert routes["home"] == "views.home"
    assert routes["account"] == "views.account"
