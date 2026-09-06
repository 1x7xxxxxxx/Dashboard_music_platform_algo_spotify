"""Guard: arriving on the setup assistant reopens step 1, not where you left off.

Type: Utility
Uses: ast, src.dashboard.views.onboarding
Triggers: pytest
Persists in: nothing

Error class `view-state-outlives-the-visit`.

Reported 2026-09-06: « quand je me balade sur l'app et que je reclique sur mise en
route, je n'ai pas automatiquement redirection vers le bienvenu ».

`_onboarding_step` lives in `session_state`, which survives navigation. An artist who
once reached step 2 reopened the assistant on « Où tu en es » for the rest of their
session — including the very first click of a later visit, which is exactly when they
wanted the welcome screen back.

Streamlit re-executes the whole script on every interaction, so a view cannot tell
"the artist just clicked my menu entry" from "the artist is on my page and clicked a
button" — the two produce identical runs. `app.py` publishes the previously rendered
page (`_page_arrived_from`), which is the only signal that separates them, and it must
be published BEFORE the sidebar renders the step links: the sidebar draws the steps
above the body, so a marker written after dispatch would leave the two halves of the
same screen disagreeing for one run.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


_APP = _repo_root() / "src" / "dashboard" / "app.py"
_VIEW = _repo_root() / "src" / "dashboard" / "views" / "onboarding.py"
_MARKER = "_page_arrived_from"


def _tree():
    return ast.parse(_APP.read_text(encoding="utf-8"))


def _app_writes_to_session(tree) -> list[tuple[int, str]]:
    """(ligne, clé) de chaque `st.session_state['…'] = …` d'app.py, par AST.

    Par l'AST et non par `"_page_arrived_from" in src` : ce fichier et `app.py`
    EXPLIQUENT tous les deux le marqueur en commentaire, donc une recherche de chaîne
    resterait verte le jour où l'écriture disparaîtrait et où seule la prose
    resterait. C'est `guard-matches-its-own-comment`, et le cliquet de
    `test_a_guard_reads_structure_not_text.py` m'a pris dessus à l'écriture.
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (isinstance(target, ast.Subscript)
                    and "session_state" in ast.unparse(target.value)
                    and isinstance(target.slice, ast.Constant)):
                out.append((node.lineno, target.slice.value))
    return out


def _app_calls(tree, name: str) -> list[int]:
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Call) and ast.unparse(n.func).endswith(name)]


def test_the_app_publishes_the_previous_page():
    written = {key for _line, key in _app_writes_to_session(_tree())}
    assert _MARKER in written, (
        f"`app.py` n'écrit plus `session_state['{_MARKER}']` : aucune vue ne peut "
        "distinguer une arrivée d'un rerun, et l'assistant rouvre là où on l'avait "
        "laissé.")


def test_the_marker_is_published_before_the_sidebar_draws_the_steps():
    """Sinon la barre et le corps affichent deux étapes différentes pendant un run."""
    tree = _tree()
    marker_lines = [ln for ln, key in _app_writes_to_session(tree) if key == _MARKER]
    step_lines = _app_calls(tree, "render_sidebar_steps")
    assert marker_lines, f"`{_MARKER}` n'est plus écrit"
    assert step_lines, "la barre latérale ne rend plus les étapes"
    assert min(marker_lines) < min(step_lines), (
        f"`{_MARKER}` (ligne {min(marker_lines)}) est posé APRÈS le rendu des étapes "
        f"(ligne {min(step_lines)}) : la barre lirait l'étape d'avant et le corps "
        "celle d'après.")


def test_the_view_resets_its_step_when_arriving_from_elsewhere():
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    show = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "show")
    src = ast.unparse(show)
    assert "_entering_from_elsewhere" in src, (
        "`show()` ne demande plus si l'on vient d'arriver — l'étape gardée en "
        "session survit à la navigation")


def test_an_absent_marker_is_not_an_arrival():
    """La subtilité qui rendrait l'assistant intraversable.

    Sans marqueur — premier run de la session, ou test headless qui appelle `show()`
    sans passer par `app.py` — traiter l'absence comme une arrivée remettrait l'étape
    à 1 à CHAQUE rerun, donc au clic même qui fait passer à l'étape 2.
    """
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_entering_from_elsewhere")
    # La comparaison `is not None` doit exister comme NŒUD, pas comme texte : une
    # docstring qui l'écrit suffirait à une recherche de chaîne, et cette fonction en
    # a une qui l'explique.
    has_none_check = any(
        isinstance(n, ast.Compare)
        and any(isinstance(op, ast.IsNot) for op in n.ops)
        and any(isinstance(c, ast.Constant) and c.value is None for c in n.comparators)
        for n in ast.walk(fn))
    assert has_none_check, (
        "`_entering_from_elsewhere` ne distingue pas « marqueur absent » de "
        "« marqueur différent » : l'assistant se remettrait à l'étape 1 à chaque clic")


def test_the_step_two_screen_offers_a_single_way_forward():
    """Quatre boutons pour trois actions, dont un doublon exact.

    `_step_status` rendait « ← Retour », « 🔑 Connecter mes sources → » et « 🏠 Aller
    au dashboard → », et `_render_landing_choice` ajoutait un SECOND « 🔑 Connecter
    mes sources → » quinze lignes plus bas, sur le même écran. Deux fonctions qui
    écrivent le même écran ne se lisent jamais ensemble.
    """
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_step_status")
    keys = [kw.value.value for n in ast.walk(fn)
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "button"
            for kw in n.keywords
            if kw.arg == "key" and isinstance(kw.value, ast.Constant)]
    assert len(keys) == 1, (
        f"{len(keys)} boutons sur l'écran « Où tu en es » ({keys}) — il n'en faut "
        "qu'un : la barre latérale porte déjà le retour aux étapes et l'accueil.")

    # Par AST, et j'ai écrit la version textuelle d'abord : elle a mordu sur le
    # COMMENTAIRE qui explique la suppression, dans ce fichier même. C'est
    # `guard-matches-its-own-comment`, pris en flagrant délit à l'écriture du garde.
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "_render_landing_choice" not in defined, (
        "`_render_landing_choice` est redéfinie : elle rendait le même bouton que "
        "`_step_status`, depuis une autre fonction — donc invisible en lisant l'une "
        "ou l'autre")
    called = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "_render_landing_choice" not in called, (
        "quelque chose appelle encore `_render_landing_choice`")
