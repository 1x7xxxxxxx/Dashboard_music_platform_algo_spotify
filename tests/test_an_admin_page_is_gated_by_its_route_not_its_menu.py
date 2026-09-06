"""Guard: hiding a page from the menu is not the same as refusing to render it.

Type: Utility
Uses: ast, src.dashboard.app
Triggers: pytest
Persists in: nothing

Error class `menu-filter-mistaken-for-an-access-gate`.

`_ADMIN_ONLY` existed since the menu was written, and was read in exactly ONE place:
the sidebar builder. `?page=admin` — a bookmark, a link in an old email, a URL typed
by hand — went straight to `_render_page`, which dispatched without asking who was
asking.

The ten pages listed happen to guard themselves, verified one by one on 2026-09-06,
and that verification corrected my own first reading: `ml_performance` checks
`session_state['role']` rather than `is_admin()`, so a grep for the function name
reported it unguarded when it is not. But ten copies in three spellings is ten places
for the eleventh page to be forgotten — and `db_health`, added to the set the same
day, had no internal guard at all.

So the list became the gate. The per-view guards stay: defence in depth costs nothing
here, and removing them would make this file the single point of failure.
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


def _tree():
    return ast.parse(_APP.read_text(encoding="utf-8"))


def _render_page_fn():
    return next(n for n in ast.walk(_tree())
                if isinstance(n, ast.FunctionDef) and n.name == "_render_page")


def _admin_only_keys() -> set[str]:
    """La liste, lue dans l'AST — sans IMPORTER `app.py`.

    L'importer était le défaut, et la CI l'a dit avant moi. `app.py` lève à l'import
    quand `FERNET_KEY` ou `AIRFLOW_PASSWORD` manquent — deux gardes de démarrage
    délibérés — et ces variables ne sont posées que sur l'étape `Run tests`. Or ce
    fichier est la signature d'une classe d'erreur, donc il tourne aussi à l'étape des
    gardes, dix étapes plus tôt, dans un environnement nu. Vert en local où un `.env`
    traîne, rouge sur le runner : c'est `guard-predicate-depends-on-the-host-env`,
    troisième instance de la semaine, et la première où je l'ai écrite moi-même.

    Lire l'AST répond exactement à la même question — quelles clés la liste
    contient-elle ? — sans rien exécuter.
    """
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(t_, "id", "") == "_ADMIN_ONLY" for t_ in node.targets):
            continue
        return {n.value for n in ast.walk(node.value)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    return set()


def test_the_admin_set_is_not_empty():
    """Sinon tout ce qui suit est vrai de rien."""
    assert len(_admin_only_keys()) >= 5, (
        f"_ADMIN_ONLY ne contient que {sorted(_admin_only_keys())}")


def test_the_dispatcher_refuses_admin_pages_to_non_admins():
    """La liste doit être LUE par le routeur, pas seulement par le menu."""
    fn = _render_page_fn()
    src = ast.unparse(fn)
    assert "_ADMIN_ONLY" in src, (
        "`_render_page` ne lit pas `_ADMIN_ONLY` : la liste ne filtre que la barre "
        "latérale, donc `?page=<clé>` rend la page à n'importe qui.")

    # Et le refus doit précéder tout rendu : une garde placée après le premier
    # `show()` laisserait la page s'afficher avant de dire non.
    guards = [n for n in fn.body
              if isinstance(n, ast.If) and "_ADMIN_ONLY" in ast.unparse(n.test)]
    assert guards, "la lecture de `_ADMIN_ONLY` n'est pas une condition de haut niveau"
    first_dispatch = next(
        (i for i, n in enumerate(fn.body)
         if isinstance(n, ast.If) and "page ==" in ast.unparse(n.test)), len(fn.body))
    assert fn.body.index(guards[0]) < first_dispatch, (
        "la garde admin est placée APRÈS le premier aiguillage : la page se rend, "
        "puis on dit non")


def test_the_gate_actually_denies_and_returns():
    """Un `st.error` sans `return` afficherait le message ET la page."""
    fn = _render_page_fn()
    guard = next(n for n in fn.body
                 if isinstance(n, ast.If) and "_ADMIN_ONLY" in ast.unparse(n.test))
    body = ast.unparse(guard)
    assert "return" in body, (
        "la garde admin n'interrompt pas le rendu — le message s'afficherait "
        "au-dessus de la page qu'il refuse")


def test_db_health_is_admin_only():
    """Demandé le 2026-09-06, et la raison vaut d'être gardée.

    Elle répond à la même question que « 🚦 Santé onboarding » — « mes données
    arrivent-elles ? » — dans le vocabulaire de l'exploitant : jeux de données,
    fraîcheur par dataset, heatmap d'import, taille des imports par semaine.
    L'artiste a déjà sa réponse, dans ses mots, sur la matrice d'état.
    """
    assert "db_health" in _admin_only_keys(), (
        "db_health est revenue au menu artiste : elle redit la matrice d'état dans "
        "le vocabulaire de la plomberie")
