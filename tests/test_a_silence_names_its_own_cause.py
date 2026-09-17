"""« Pas assez d'historique » n'est pas « rien dans cette fenêtre ».

Type: Test
Uses: ast, re
Depends on: src/dashboard/views/*.py
Persists in: nothing

Les deux silences demandent des GESTES OPPOSÉS. Le premier fait attendre ; le second
demande un import. Un message qui se trompe de cause envoie l'artiste chercher le
mauvais geste, et rien sur la figure ne le détrompe.

Trouvé une première fois le 2026-09-12 au navigateur, sur l'accueil : « pas encore
assez d'historique » à un locataire qui a **quatre ans** de mesures, parce que le CSV
Spotify n'avait pas été déposé depuis 92 jours. Corrigé dans `home.py` seul.

Trouvé une **seconde** fois le 2026-09-17 en balayant la classe, et c'est le point de
ce fichier : `views/apple_music.py:216` portait exactement le même message, sous une
requête exactement aussi fenêtrée (`window.sql_between("date")`), et personne ne
l'avait relu parce que la classe portait le nom de l'accueil.

Le prédicat, et pourquoi il regarde la REQUÊTE
----------------------------------------------
Une vue est concernée quand elle réunit deux choses : un message qui accuse un manque
d'HISTORIQUE, et une requête bornée par une FENÊTRE. Sans fenêtre, le message est
vrai ; sans message d'historique, la question ne se pose pas. On exige alors que la
vue distingue les deux cas — ce qui se lit à la présence d'une comparaison de la
dernière mesure avec le début de la fenêtre.

⚠️ La distinction ne peut pas être « la vue contient deux messages » : deux messages
peuvent dire la même chose. Ce qui la prouve est la LECTURE hors fenêtre, donc une
comparaison `< window.start` (ou `< since`). C'est structurel, pas textuel.

Ce qu'il ne couvre PAS
----------------------
Les vues dont la fenêtre est implicite (un `WHERE date >= CURRENT_DATE - N` écrit à la
main plutôt que par `PeriodWindow`) : le prédicat ne les voit pas. Et il ne juge pas le
TEXTE des deux messages — il exige qu'ils soient distingués, pas qu'ils soient bons.

Mutation record — 2026-09-17 : en retirant la comparaison `_last < window.start` de
`apple_music.py`, ce garde le nomme ; en retirant celle de `home.py`, il nomme
`home`. Remises, il passe.

---
rex: []
---
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src" / "dashboard" / "views"
_UI = _ROOT / "src" / "dashboard" / "utils" / "ui.py"

# La décision vit dans UN endroit depuis le 2026-09-17. Une vue satisfait ce garde
# soit en comparant elle-même, soit en DÉLÉGUANT ici — et le test suivant interdit
# que la délégation devienne une échappatoire, en exigeant que le délégué compare.
_DELEGATE = "say_why_it_is_empty"

# Un message qui accuse la JEUNESSE du compte. On cherche la clé i18n, pas la phrase :
# la phrase est traduite, la clé ne l'est pas.
_YOUTH = re.compile(r"(not_enough_history|no_history|trend_no_series|"
                    r"pas (encore )?assez d'historique|not enough history)", re.I)

# La preuve qu'une vue distingue les deux silences : elle compare la dernière mesure
# au début de la fenêtre. Textuellement impossible à contrefaire par un commentaire —
# c'est une `ast.Compare` entre un nom et un attribut de fenêtre.
_WINDOW_STARTS = ("start", "since")


def _reads_a_window(src: str) -> bool:
    return "sql_between" in src or "period_filter" in src


def _compares_against_a_window_start(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and (getattr(node.func, "id", "") or getattr(node.func, "attr", ""))
                == _DELEGATE):
            return True
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(o, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for o in node.ops):
            continue
        for side in [node.left, *node.comparators]:
            if isinstance(side, ast.Attribute) and side.attr in _WINDOW_STARTS:
                return True
            if isinstance(side, ast.Name) and side.id in _WINDOW_STARTS:
                return True
    return False


def _views_claiming_youth() -> list[str]:
    out = []
    for path in sorted(_VIEWS.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        src = path.read_text(encoding="utf-8")
        if not _YOUTH.search(src) or not _reads_a_window(src):
            continue
        out.append(str(path.relative_to(_ROOT)).replace("\\", "/"))
    return out


def test_the_population_is_not_empty() -> None:
    """Anti-vacuité : sans vue concernée, tout ce fichier est vert sur rien."""
    views = _views_claiming_youth()
    assert len(views) >= 2, (
        f"seulement {len(views)} vue(s) réunissent « message d'historique » et "
        "« requête fenêtrée » — il y en avait 2 le 2026-09-17 (`home.py`, "
        "`apple_music.py`). Soit les clés i18n ont changé de nom, soit le prédicat "
        "est cassé ; dans les deux cas le test d'à côté ne garde plus rien.")


def test_a_view_that_blames_history_can_tell_an_empty_window_apart() -> None:
    muettes = []
    for rel in _views_claiming_youth():
        tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
        if not _compares_against_a_window_start(tree):
            muettes.append(rel)
    assert not muettes, (
        f"{len(muettes)} vue(s) accusent un manque d'HISTORIQUE sous une requête "
        "FENÊTRÉE, sans jamais comparer la dernière mesure au début de la fenêtre.\n"
        "Un artiste qui a des années de données et une fenêtre vide y lit que son "
        "compte est trop jeune — et attend, au lieu de déposer un export.\n"
        "Remède : relire la série SANS la fenêtre dans la branche vide, et comparer "
        "(`home.py:546`, `apple_music.py:231`).\n  " + "\n  ".join(muettes))


def test_the_delegate_is_the_one_that_compares() -> None:
    """Déléguer n'est pas s'exempter.

    Le test ci-dessus accepte qu'une vue appelle `say_why_it_is_empty` au lieu de
    comparer. Sans ce test-ci, vider le helper rendrait les quatre vues vertes d'un
    coup — la forme exacte d'« un garde satisfait par la présence d'un nom ».
    """
    tree = ast.parse(_UI.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == _DELEGATE), None)
    assert fn is not None, (
        f"`{_DELEGATE}` a disparu de `utils/ui.py` : les vues qui lui délèguent la "
        "distinction des deux silences ne la font plus, et le test d'à côté les "
        "accepte toutes.")
    assert _compares_against_a_window_start(
        ast.Module(body=fn.body, type_ignores=[])), (
        f"`{_DELEGATE}` ne compare plus la dernière mesure au début de la fenêtre : "
        "il rend donc toujours le même message, et les quatre vues qui lui délèguent "
        "sont vertes sur le défaut.")
