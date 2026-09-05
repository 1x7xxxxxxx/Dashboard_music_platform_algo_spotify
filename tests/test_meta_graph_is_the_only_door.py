"""Une seule porte vers l'API Graph, et une seule écriture de sa version.

Type: Test
Uses: ast
Depends on: src/utils/meta_config.py, src/utils/meta_graph.py
Persists in: —

`meta_config.py` affirme dans son propre docstring : « Update META_API_VERSION here —
**no other file needs to change** ». C'était faux. `central_apps.check_meta` écrivait
`https://graph.facebook.com/v21.0/` en dur dans ses DEUX appels — ceux qui décident si
l'app de la plateforme est vivante — pendant que la constante était passée à `v24.0`.
Trois versions d'écart, pendant des mois, sur le chemin qui tourne toutes les nuits.

Personne ne l'a vu parce que **rien ne reliait les deux écritures**. Ce test est ce
lien. Il ne vérifie pas « la version est-elle la bonne ? » — question sans réponse
stable — mais « existe-t-il un second endroit où elle puisse diverger ? ».

Lecture par AST en excluant les docstrings : celui de `meta_graph.py` cite l'URL
fautive pour expliquer le défaut, et une recherche de chaîne serait rouge sur sa propre
explication (`guard-matches-its-own-comment`).
"""
import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
# Le seul fichier autorisé à écrire l'hôte : celui qui construit la constante.
_THE_DOOR = "src/utils/meta_config.py"


def _string_constants(path: Path):
    """Les chaînes du code, docstrings exclues."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and n.body and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
        and isinstance(n.body[0].value.value, str)
    }
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings):
            yield node.lineno, node.value


def test_only_meta_config_writes_the_graph_host():
    root = _SRC.parent
    offenders = []
    for path in sorted(_SRC.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel == _THE_DOOR:
            continue
        for lineno, value in _string_constants(path):
            if "graph.facebook.com" in value:
                offenders.append(f"{rel}:{lineno} — {value[:70]!r}")
    assert not offenders, (
        "l'hôte Graph est écrit ailleurs que dans `meta_config.py`, donc la version "
        "d'API peut diverger sans que rien ne le dise — c'est exactement ce qui est "
        "arrivé à `central_apps.check_meta` (v21 contre v24) :\n  "
        + "\n  ".join(offenders))


def test_the_version_is_declared_once_and_the_base_url_derives_from_it():
    from src.utils.meta_config import META_API_VERSION, META_GRAPH_BASE_URL

    assert META_GRAPH_BASE_URL.endswith(META_API_VERSION), (
        "l'URL de base ne dérive plus de la version : les deux peuvent diverger")
    # Épinglé sur la RELATION, jamais sur la valeur — `v24.0` changera.
    assert META_API_VERSION.startswith("v")


def test_the_client_never_surfaces_the_token_it_sends():
    """Le jeton voyage en query string : un corps d'erreur ou une exception réseau
    embarque l'URL préparée. Aucun des deux ne doit ressortir tel quel."""
    import inspect

    from src.utils import meta_graph

    src = inspect.getsource(meta_graph)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "text":
            owner = getattr(node.value, "id", "")
            assert owner != "r", (
                "`r.text` remonte dans un message d'erreur : il contient l'URL "
                "préparée, donc le jeton System User de la flotte")
    # Et `str(exc)` d'une exception requests, pour la même raison.
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "str"
                and node.args and getattr(node.args[0], "id", "") == "exc"):
            raise AssertionError("`str(exc)` sur une exception réseau expose l'URL")


def test_the_door_is_actually_used():
    """Une porte que personne ne franchit n'est pas une porte.

    `meta_graph.py` a été écrit, testé et gardé le 2026-09-05 **sans aucun appelant**
    en production. C'est la forme la plus discrète de dette : le module a l'air d'être
    la règle, il ne l'est nulle part, et il diverge du code réel jusqu'au jour où on
    le branche — quatre divergences accumulées la dernière fois que c'est arrivé.
    """
    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    callers = []
    for path in sorted(src.rglob("*.py")):
        if path.name == "meta_graph.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("meta_graph"):
                callers.append(path.relative_to(src.parent).as_posix())
                break
    assert callers, (
        "`src/utils/meta_graph.py` n'est importé par aucun module de `src/` : il est "
        "écrit, gardé, et débranché")
