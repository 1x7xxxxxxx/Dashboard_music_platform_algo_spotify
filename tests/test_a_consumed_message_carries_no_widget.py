"""Guard: un message consommé à l'affichage ne peut pas porter de widget interactif.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Error class `consumed-state-hides-its-own-widget`.

Le motif est partout dans ce dépôt, et il est JUSTE pour un message :

    _last = st.session_state.pop(KEY, None)
    if _last:
        st.success("✅ Import exécuté …")

`st.rerun()` efface tout ce qui a été écrit avant lui, donc un compte rendu voyage
par la session ; et on le consomme (`pop`) pour qu'il ne réapparaisse pas à chaque
rerun, des jours plus tard, en contredisant l'état.

Il devient FAUX dès que le bloc porte un bouton, et le mécanisme est celui de
Streamlit : un clic ne se lit pas au moment du clic. Il déclenche un rerun, et
`st.button(...)` ne rend `True` que si le widget est **ré-instancié au même endroit**
pendant ce rerun. Or la valeur a été consommée au rendu PRÉCÉDENT : au rerun du clic,
`pop` rend `None`, le bloc est sauté, le bouton n'existe pas, et le clic est jeté.

Signalé le 2026-09-08, sur le geste qui termine l'import de CSV : « quand je clique
sur configurer le mapping, ça me renvoie nulle part ». Deux sites portaient la même
forme, tous deux au bout d'un parcours de mise en route :

* `upload_csv._render_after_import` → `_render_mapping_cta` — « 🔗 Confirmer le nom
  des titres » après un import réussi ;
* `credentials/_render.render_save_verdict` → `_render_next_step` — « 🏠 Aller au
  dashboard → » après la dernière plateforme connectée.

Le garde suit les APPELS, pas le seul bloc lexical : dans les deux cas le bouton est
à un ou deux appels du `pop`, et un garde qui ne lirait que le corps du `if` les
aurait tous les deux déclarés propres.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path("src/dashboard")

# Les widgets dont la VALEUR se lit au rerun suivant : ils doivent être
# ré-instanciés pour que le geste de l'utilisateur soit vu. `st.link_button`,
# `st.markdown`, `st.success` n'en sont pas — ils n'ont rien à rendre.
_INTERACTIVE = frozenset({
    "button", "download_button", "form_submit_button", "data_editor",
    "checkbox", "toggle", "radio", "selectbox", "multiselect",
    "text_input", "text_area", "number_input", "slider", "date_input",
    "time_input", "file_uploader", "color_picker", "camera_input",
})


def _is_session_state_pop(node: ast.AST) -> bool:
    """`st.session_state.pop(...)` — lu sur la structure, pas sur le texte."""
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == "pop"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "session_state")


def _interactive_calls(node: ast.AST) -> list[tuple[int, str]]:
    """Les appels de widget interactif portés par ce sous-arbre."""
    out = []
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr in _INTERACTIVE
                and isinstance(sub.func.value, ast.Name)
                and sub.func.value.id == "st"):
            out.append((sub.lineno, sub.func.attr))
    return out


def _local_calls(node: ast.AST) -> set[str]:
    """Les fonctions du MÊME module appelées depuis ce sous-arbre."""
    return {sub.func.id for sub in ast.walk(node)
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)}


def _functions(tree: ast.AST) -> dict:
    return {n.name: n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _reachable_widgets(node: ast.AST, funcs: dict, seen: set) -> list[tuple[int, str]]:
    """Les widgets atteignables depuis `node`, en suivant les appels du module.

    C'est la moitié qui compte. Le défaut du 2026-09-08 avait son `pop` dans
    `render_uploader` et son bouton dans `_render_mapping_cta`, deux appels plus
    loin : un garde lisant le seul corps du `if` aurait rendu vert sur le défaut.
    """
    found = list(_interactive_calls(node))
    for name in _local_calls(node):
        if name in seen or name not in funcs:
            continue
        seen.add(name)
        found += _reachable_widgets(funcs[name], funcs, seen)
    return found


def _consumed_blocks(tree: ast.AST) -> list[ast.AST]:
    """Les régions gardées par une valeur que `session_state.pop` a consommée.

    Deux formes, les deux employées dans ce dépôt :

        if st.session_state.pop(KEY, None):   → le test porte le pop
        x = st.session_state.pop(KEY, None)   → le pop est lié, puis testé
        if x: ...
    """
    blocks = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        popped: set[str] = set()
        for node in ast.walk(fn):
            if (isinstance(node, ast.Assign) and _is_session_state_pop(node.value)
                    and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
                popped.add(node.targets[0].id)
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            names = {s.id for s in ast.walk(node.test) if isinstance(s, ast.Name)}
            if any(_is_session_state_pop(c) for c in ast.walk(node.test)) or (names & popped):
                blocks += node.body
        # `pending = st.session_state.get(K); if not pending: return;
        #  st.session_state.pop(K)` — le pop nu au fil de la fonction consomme
        # tout ce qui SUIT, pas un bloc. C'est la forme de `render_save_verdict`.
        for i, stmt in enumerate(fn.body):
            if isinstance(stmt, ast.Expr) and _is_session_state_pop(stmt.value):
                blocks += fn.body[i + 1:]
    return blocks


def _offenders() -> list[str]:
    out = []
    for path in sorted(_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        funcs = _functions(tree)
        for block in _consumed_blocks(tree):
            for lineno, widget in _reachable_widgets(block, funcs, set()):
                out.append(f"{path}:{lineno}: st.{widget} dans un bloc consommé par pop()")
    return sorted(set(out))


def test_no_interactive_widget_lives_in_a_consumed_block():
    """Un bouton dans un bloc consommé est un bouton mort — le clic est jeté."""
    offenders = _offenders()
    assert not offenders, (
        "Widget interactif rendu dans un bloc que `session_state.pop` a consommé.\n"
        "Le clic déclenche un rerun ; au rerun le pop rend None, le widget n'est pas\n"
        "ré-instancié, et le geste est perdu. Rendre le widget HORS du bloc consommé,\n"
        "ou lire la valeur avec `get` et la consommer sur le geste.\n  "
        + "\n  ".join(offenders))


@pytest.mark.parametrize("source, expect_hit", [
    # Le défaut, dans sa forme minimale.
    ("import streamlit as st\n"
     "def f():\n"
     "    x = st.session_state.pop('k', None)\n"
     "    if x:\n"
     "        st.button('go')\n", True),
    # Le même, à un appel de distance — la forme réelle des deux défauts.
    ("import streamlit as st\n"
     "def g():\n"
     "    st.button('go')\n"
     "def f():\n"
     "    x = st.session_state.pop('k', None)\n"
     "    if x:\n"
     "        g()\n", True),
    # Un message consommé SANS widget : c'est le motif juste, il reste vert.
    ("import streamlit as st\n"
     "def f():\n"
     "    x = st.session_state.pop('k', None)\n"
     "    if x:\n"
     "        st.success('ok')\n", False),
    # Un bouton hors du bloc consommé : correct, il est ré-instancié à chaque rendu.
    ("import streamlit as st\n"
     "def f():\n"
     "    x = st.session_state.pop('k', None)\n"
     "    if x:\n"
     "        st.success('ok')\n"
     "    st.button('go')\n", False),
])
def test_the_guard_sees_the_shape_not_the_words(source, expect_hit):
    """Le prédicat lui-même, sur quatre formes — dont les deux qui doivent rester vertes."""
    tree = ast.parse(source)
    funcs = _functions(tree)
    hits = [w for block in _consumed_blocks(tree)
            for w in _reachable_widgets(block, funcs, set())]
    assert bool(hits) is expect_hit
