"""Un `@st.fragment` s'exécute APRÈS que la vue a fermé sa connexion.

Type: Test
Uses: ast, pathlib
Depends on: src/dashboard/views/*.py
Persists in: nothing

Le danger, et pourquoi il n'est pas visible en lisant le code
--------------------------------------------------------------
`st.fragment` change **quand** une fonction s'exécute, pas ce qu'elle fait. Le corps
décoré est rejoué seul, plus tard, à chaque fois que l'un de ses widgets bouge — des
minutes après que `show()` est rentrée et que son `finally` a fermé la connexion.

Une fonction qui prend `db` en argument est donc parfaitement correcte au premier rendu
et **casse au second**, avec une erreur (`connection already closed`) qui ne nomme ni le
fragment ni le filtre qu'on vient de bouger. Le lien entre le geste et la panne est
invisible : c'est ce qui rend la classe chère, pas la panne elle-même.

C'est la forme temporelle de `du-code-correct-que-rien-n-atteint` : ici le code est
atteint, mais dans un état du monde que son auteur n'a jamais vu.

La règle
--------
**Une fonction décorée `@st.fragment` ne reçoit ni connexion ni curseur.** Elle reçoit
des données déjà chargées — un DataFrame, une liste, un dict. Si un fragment a besoin de
relire la base, il ouvre SA propre connexion dans son corps et la ferme : c'est alors un
choix explicite, visible, et pas une capture accidentelle.

R118 pose des fragments sur onze vues à filtres. Écrire ce garde AVANT la deuxième vue
est le seul moment où il coûte zéro.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src" / "dashboard" / "views"

# Les noms d'argument qui portent une connexion dans ce dépôt. Le mot `db` est le
# précédent dominant ; `conn`, `cursor` et `handler` sont les variantes rencontrées.
_CONNECTION_ARGS = {"db", "db2", "conn", "connection", "cur", "cursor", "handler",
                    "pg", "postgres"}

# Ce qu'on ne doit pas APPELER non plus depuis un fragment, même sans le recevoir.
# `project_db` ajouté le 2026-09-16 : c'est le gestionnaire de contexte de
# `spotify_s4a_combined`, et l'omettre aurait laissé passer un fragment qui ouvre.
_CONNECTION_OPENERS = {"get_db_connection", "view_session", "tenant_scope",
                       "project_db"}


def _is_fragment(node: ast.AST) -> bool:
    for dec in getattr(node, "decorator_list", []):
        target = dec.func if isinstance(dec, ast.Call) else dec
        name = (target.attr if isinstance(target, ast.Attribute)
                else target.id if isinstance(target, ast.Name) else None)
        if name in {"fragment", "experimental_fragment"}:
            return True
    return False


def _fragments() -> list[tuple[Path, ast.FunctionDef]]:
    out = []
    for path in sorted(_VIEWS.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_fragment(n):
                out.append((path, n))
    return out


def test_no_fragment_receives_a_connection() -> None:
    offenders = []
    for path, fn in _fragments():
        args = [a.arg for a in fn.args.args + fn.args.kwonlyargs]
        bad = sorted(set(args) & _CONNECTION_ARGS)
        if bad:
            offenders.append(
                f"{path.relative_to(_ROOT)}:{fn.lineno} `{fn.name}` reçoit {bad}")

    assert not offenders, (
        "fragment(s) recevant une connexion :\n  " + "\n  ".join(offenders)
        + "\n\nUn fragment est rejoué SEUL, plus tard, à chaque mouvement de ses widgets "
          "— après que `show()` a fermé la connexion dans son `finally`. Il est donc "
          "correct au premier rendu et casse au second, avec une erreur qui ne nomme ni "
          "le fragment ni le filtre qu'on vient de bouger.\n"
          "Passer les DONNÉES déjà chargées (DataFrame, liste, dict), ou ouvrir et "
          "fermer une connexion DANS le corps du fragment — ce qui est alors un choix "
          "visible et pas une capture.")


def test_no_fragment_opens_a_connection_it_does_not_close() -> None:
    """Ouvrir dans le fragment est permis — ne pas fermer ne l'est pas.

    C'est la porte de sortie de la règle ci-dessus, et une porte de sortie sans garde
    devient le chemin par défaut. Le dépôt compte une connexion par rendu
    (`tests/test_view_connection_budget.py`) ; un fragment qui en ouvre une à chaque
    mouvement de filtre, sans la rendre, épuise le pool à `maxconn=10` en dix clics — et
    la jauge `direct_fallback` le dirait après coup, jamais avant.
    """
    offenders = []
    for path, fn in _fragments():
        opens = [n for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id in _CONNECTION_OPENERS]
        if not opens:
            continue
        # `with view_session() as ...` et `with get_db_connection() as ...` ferment seuls.
        managed = any(
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Name)
            and item.context_expr.func.id in _CONNECTION_OPENERS
            for w in ast.walk(fn) if isinstance(w, ast.With)
            for item in w.items)
        closes = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "close" for n in ast.walk(fn))
        if not managed and not closes:
            offenders.append(
                f"{path.relative_to(_ROOT)}:{fn.lineno} `{fn.name}` ouvre "
                f"{sorted({o.func.id for o in opens})} et ne ferme rien")

    assert not offenders, (
        "fragment(s) ouvrant une connexion sans la rendre :\n  " + "\n  ".join(offenders)
        + "\n\nUn fragment se rejoue à CHAQUE mouvement de filtre. Le pool est à "
          "`maxconn=10` : dix clics suffisent. Utiliser `with view_session() as (db, "
          "artist_id):`, qui ferme par construction.")


def test_the_detector_sees_a_fragment_and_its_arguments() -> None:
    """Non-vacuité, sur les DEUX moitiés : trouver les fragments, et lire leurs args.

    Sans elle, un décorateur écrit autrement — `@st.experimental_fragment`, ou importé
    sous un autre nom — rendrait les deux tests ci-dessus verts à vide, sur un dépôt qui
    en posera onze.
    """
    found = _fragments()
    assert found, (
        "aucun `@st.fragment` trouvé sous `views/` — la détection est cassée, ou R118 a "
        "été défaite. Les deux tests ci-dessus ne prouveraient rien.")

    src = "import streamlit as st\n@st.fragment\ndef f(db, df): pass\n"
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    assert _is_fragment(fn), "le décorateur `@st.fragment` n'est plus reconnu"
    assert set(a.arg for a in fn.args.args) & _CONNECTION_ARGS == {"db"}, (
        "la lecture des arguments ne voit plus une connexion passée en clair")

    src2 = "import streamlit as st\n@st.experimental_fragment\ndef g(df): pass\n"
    fn2 = next(n for n in ast.walk(ast.parse(src2)) if isinstance(n, ast.FunctionDef))
    assert _is_fragment(fn2), "la forme `@st.experimental_fragment` échappe au détecteur"
