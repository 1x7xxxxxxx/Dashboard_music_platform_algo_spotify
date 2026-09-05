"""L'artiste ne peut pas donner sa chaîne « — Topic ». C'est nous qui la trouvons.

Un artiste distribué a DEUX chaînes YouTube :

  * la principale, celle où il publie ;
  * la « … - Topic », auto-générée par YouTube pour sa musique distribuée.

Mesuré le 2026-09-05 sur FJAAK : 53 vidéos / 11 M vues d'un côté, 172 vidéos /
880 k vues de l'autre. **Aucune ne remplace l'autre.**

Le défaut : le champ demandait « la chaîne « — Topic » », alors que
`youtube.com/account_advanced` — le seul écran où un artiste lit un identifiant de
chaîne — ne montre QUE la principale. La Topic n'appartient pas à son compte Google
et n'y figure jamais. On demandait donc une valeur introuvable depuis l'écran qu'on
indiquait, ce qui est la classe `instruction-assumes-visibility-the-reader-does-not-have`.

Trois choses gardées, et la troisième est celle qui manque toujours ailleurs :
  1. la sélection n'accepte qu'une ÉGALITÉ de titre — jamais un « à peu près » ;
  2. la découverte est branchée sur la SAUVEGARDE, pas seulement définie ;
  3. le DAG collecte réellement les deux chaînes.
"""
import ast
import pathlib

import pytest

from src.dashboard.utils.youtube_channel import pick_topic_channel

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_RENDER = _ROOT / "src/dashboard/views/credentials/_render.py"
_DAG = _ROOT / "airflow/dags/youtube_daily.py"


def _fn(path: pathlib.Path, name: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(n, ast.FunctionDef) and n.name == name)


# Les vrais titres renvoyés par `search.list` pour « FJAAK - Topic », 2026-09-05.
# Épingler la RÉALITÉ, pas une forme inventée par le test : le troisième résultat
# est une Topic d'un AUTRE artiste, et c'est exactement ce qui doit être refusé.
_REAL_RESULTS = [
    ("FJAAK - Topic", "UCE0AHir0yNpTMK4niSTDF7Q"),
    ("FJAAK", "UCiMOvinn6mbmAwbXTS_nHPg"),
    ("HeCTA - Topic", "UCyafn7JZm7lNJ63n6qiCazw"),
    ("Modeselektor - Topic", "UCOinH_vPmoy7pXYMdkRMMAQ"),
]


def test_only_an_exact_title_is_accepted():
    assert pick_topic_channel("FJAAK", _REAL_RESULTS) == (
        "UCE0AHir0yNpTMK4niSTDF7Q", "FJAAK - Topic")


@pytest.mark.parametrize("title,why", [
    ("FJAA", "un préfixe n'est pas le même artiste"),
    ("FJAAK Official", "un titre plus long non plus"),
    (None, "sans titre de chaîne principale, on ne cherche rien"),
    ("", "idem pour une chaîne vide"),
])
def test_a_near_miss_is_refused(title, why):
    """Une identité devinée fait collecter le catalogue de quelqu'un d'autre.

    C'est la classe que ce dépôt a passé deux séances à retirer, et une recherche
    par nom y a déjà été mesurée non fiable : pour Benken, la bonne chaîne n'était
    pas dans les cinq premiers résultats.
    """
    assert pick_topic_channel(title, _REAL_RESULTS) is None, why


def test_the_discovery_is_wired_to_the_save_and_not_only_defined():
    """Une couche définie que rien n'appelle ne collecte rien.

    Trois couches de ce dépôt ont déjà été trouvées présentes et débranchées, dont
    `topic_channel_query`, qui n'avait AUCUN appelant de production avant ce jour —
    seulement un test. La question gardée est « la sauvegarde l'atteint-elle ? ».
    """
    fn = _fn(_RENDER, "_handle_save")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "discover_topic_channel"]
    assert calls, "`_handle_save` ne cherche jamais la chaîne Topic"

    for call in calls:
        for node in ast.walk(fn):
            if (isinstance(node, ast.If) and isinstance(node.test, ast.Constant)
                    and not node.test.value
                    and any(n is call for n in ast.walk(node))):
                pytest.fail("la découverte est sous une branche morte")

    stored = [n for n in ast.walk(fn)
              if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
              and n.slice.value == "topic_channel_id"]
    assert stored, (
        "la chaîne Topic est trouvée puis jetée : sans écriture dans `extra`, le "
        "DAG ne la verra jamais")


def test_the_dag_collects_both_channels():
    """Découvrir sans collecter n'aurait rien changé pour l'artiste."""
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    # Lu en AST, jamais en texte : mon premier jet cherchait la chaîne
    # « topic_channel_id » dans le source, et le commentaire qui explique cette
    # collecte la contient — le garde aurait été vert sur sa propre explication.
    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get"
             and n.args and isinstance(n.args[0], ast.Constant)
             and n.args[0].value == "topic_channel_id"]
    assert reads, (
        "le DAG ne LIT pas `topic_channel_id` : la chaîne Topic serait enregistrée "
        "à la saisie et jamais collectée")
    collects = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") == "collect_all_data"]
    assert collects, "le DAG ne collecte plus rien"
    # L'appel doit être dans la boucle DES CHAÎNES, pas simplement « dans une
    # boucle ». Première écriture de ce test : « il existe un `for` qui contient
    # l'appel » — vert sur son propre mutant, parce que la boucle des ARTISTES
    # l'englobe aussi. On vise donc la boucle la plus proche, et on regarde sur
    # quoi elle itère.
    enclosing = [n for n in ast.walk(tree) if isinstance(n, ast.For)
                 and any(c is collects[0] for c in ast.walk(n))]
    assert enclosing, "la collecte n'est plus dans aucune boucle"
    nearest = max(enclosing, key=lambda n: n.lineno)
    iterated = ast.unparse(nearest.iter)
    assert "channel" in iterated.lower(), (
        f"la collecte est bien dans une boucle, mais elle itère sur `{iterated}` — "
        "pas sur les chaînes. Une seule des deux serait collectée.")
