"""Guard: rien ne s'écrit à l'écran avant un `st.rerun()` — il efface tout.

Type: Utility
Uses: ast, src.dashboard.views.upload_csv, src.dashboard.app
Triggers: pytest
Persists in: nothing

Error class `message-written-before-a-rerun`.

Streamlit ré-exécute le script de zéro sur `st.rerun()`. Tout `st.success`,
`st.warning`, `st.caption` ou `st.dataframe` posé AVANT lui, dans le même passage,
n'est jamais vu. Ce dépôt l'a payé trois fois :

* le verdict de sauvegarde des credentials (passé par `VERDICT_KEY`) ;
* le démarrage automatique de la collecte (passé par `AUTOSTART_KEY`) ;
* le 2026-09-06, six messages du bloc d'import CSV — collecte démarrée, référentiel
  de sorties, agrégations iMusician et DistroKid — au moment où vider la zone de
  dépôt a imposé un rerun à la fin du même bloc.

Le mode d'échec est muet dans les deux sens : le code est correct, la fonction
appelée fait son travail, et l'écran est simplement vide. Aucun test de rendu ne
le voit, puisque le rendu est bien produit — puis jeté.

La parade est toujours la même : accumuler, poser en session, rendre après.
"""
from __future__ import annotations

import ast
import functools
import pathlib

import pytest

_VIEW = pathlib.Path("src/dashboard/views/upload_csv.py")

# Ce qui ÉCRIT à l'écran. `st.button`, `st.text_input`, `st.selectbox` sont des
# widgets : leur valeur est relue au passage suivant, ils ne perdent rien.
_WRITERS = {"success", "warning", "error", "info", "caption", "dataframe",
            "metric", "subheader", "markdown", "table", "write"}


@functools.lru_cache(maxsize=1)
def _tree() -> ast.Module:
    """L'AST de la vue, lu à l'appel — jamais à l'import (cliquet du dépôt)."""
    return ast.parse(_VIEW.read_text(encoding="utf-8"))


def _blocks_containing_a_rerun() -> list[ast.stmt]:
    """Les blocs `if`/`for` dont le corps se termine par un `st.rerun()`."""
    found = []
    for node in ast.walk(_tree()):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        last = body[-1]
        if (isinstance(last, ast.Expr) and isinstance(last.value, ast.Call)
                and isinstance(last.value.func, ast.Attribute)
                and last.value.func.attr == "rerun"):
            found.append(node)
    return found


def test_the_view_still_reruns_somewhere():
    """Sans rerun, ce garde ne mesure rien — et la zone de dépôt ne se vide plus."""
    assert _blocks_containing_a_rerun(), (
        "aucun bloc ne se termine par `st.rerun()` dans la vue. Soit le vidage de la "
        "zone de dépôt a disparu, soit ce garde regarde le mauvais fichier."
    )


def test_no_screen_output_precedes_a_rerun():
    offenders = []
    for block in _blocks_containing_a_rerun():
        for stmt in block.body[:-1]:
            for node in ast.walk(stmt):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr in _WRITERS
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "st"):
                    offenders.append(f"st.{node.func.attr} ligne {node.lineno}")

    assert not offenders, (
        "écrit à l'écran puis relance le script, qui efface tout : "
        + ", ".join(offenders)
        + ". Accumule le message, pose-le en session, rends-le APRÈS le rerun — "
        "c'est la parade déjà en place pour le verdict de sauvegarde et pour le "
        "démarrage automatique de la collecte."
    )


def _navigation_targets(tree: ast.AST) -> set:
    """Les pages que cette vue vise, quelle que soit la FORME de la navigation.

    Deux formes coexistent dans ce dépôt, et un garde qui n'en lit qu'une se rend
    aveugle au jour où l'autre est adoptée :

    * `st.session_state['_nav_page'] = 'x'` — la forme brute ;
    * `goto('x')` — `utils/navigation.py`, qui retire en plus `?page=`.

    Le 2026-09-08 la vue est passée de la première à la seconde et ce garde a échoué
    sur son propre message « garde à repointer » : il ne mesurait plus rien, mais il
    l'a DIT au lieu de passer au vert sur zéro site. C'est la seule différence qui
    compte entre un garde périmé et un garde qui ment.
    """
    targets = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            for target in node.targets:
                if (isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Attribute)
                        and target.value.attr == "session_state"
                        and isinstance(target.slice, ast.Constant)
                        and target.slice.value == "_nav_page"):
                    targets.add(node.value.value)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "goto" and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            targets.add(node.args[0].value)
    return targets


def test_the_mapping_button_targets_a_real_page():
    """Un bouton qui vise une page inexistante mène à l'accueil."""
    targets = _navigation_targets(_tree())
    assert targets, "aucun bouton de navigation dans la vue — garde à repointer"

    app = pathlib.Path("src/dashboard/app.py").read_text(encoding="utf-8")
    app_tree = ast.parse(app)
    routed = {
        cmp.value
        for node in ast.walk(app_tree) if isinstance(node, ast.Compare)
        for cmp in node.comparators
        if isinstance(cmp, ast.Constant) and isinstance(cmp.value, str)
    }
    for page in targets:
        assert page in routed, (
            f"la vue envoie l'artiste sur `{page}`, qu'`app.py` ne route pas : il "
            "atterrira sur l'accueil sans comprendre pourquoi."
        )


@pytest.mark.parametrize("name", ["_clear_uploader", "_uploader_key"])
def test_the_drop_zone_can_be_emptied(name):
    """Streamlit n'a pas d'API pour vider un file_uploader — la clé le fait."""
    fns = {n.name for n in ast.walk(_tree()) if isinstance(n, ast.FunctionDef)}
    assert name in fns, (
        f"`{name}` a disparu : sans clé variable, les fichiers importés restent "
        "affichés dans la zone de dépôt et l'écran se lit « rien n'est parti »."
    )
