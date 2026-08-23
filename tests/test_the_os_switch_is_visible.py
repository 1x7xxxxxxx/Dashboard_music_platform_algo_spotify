"""
Guard — le sélecteur Mac/Windows doit être rendu par le chemin QUI TOURNE.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: src/dashboard/content/credential_guides_st.py, src/dashboard/utils/os_hints.py
Persists in: nothing

Error class: the-feature-is-wired-to-the-function-nobody-calls.

Mesuré le 2026-08-23. `utils/os_hints.py` existe, avec sa substitution de jetons
(`{{VIEW_SOURCE}}`, `{{FIND}}`, `{{COPY}}`…) et un `os_selector()` complet. Mais
`os_selector()` n'était appelé que depuis `render_credential_guides()` — **qui n'a aucun
appelant**. Le chemin réellement emprunté par les onglets,
`render_credential_guide_for()`, résolvait les jetons par **reniflage du User-Agent avec
WINDOWS par défaut**, sans offrir de correction.

Un artiste Mac (GRiNCH, 12/08) lisait donc des raccourcis Windows, sans bouton pour
changer. La fonctionnalité était écrite, traduite, testée — et branchée sur la porte que
personne n'ouvre.

Le garde ne teste pas que `os_selector` existe : il teste qu'il est appelé depuis la
fonction que les onglets utilisent réellement. C'est la seule question qui compte.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ST = _ROOT / "src" / "dashboard" / "content" / "credential_guides_st.py"
_HINTS = _ROOT / "src" / "dashboard" / "utils" / "os_hints.py"
# La fonction que les onglets appellent — vérifiée ci-dessous, pas supposée.
_LIVE_RENDERER = "render_credential_guide_for"


def _fn(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == name), None)


def test_the_os_selector_still_exists():
    assert _fn(_HINTS, "os_selector") is not None, (
        "`os_selector` a disparu de os_hints.py"
    )


def test_the_live_renderer_is_the_one_the_tabs_use():
    """Si les onglets changent de porte d'entrée, ce garde doit tomber, pas mentir."""
    render = (_ROOT / "src" / "dashboard" / "views" / "credentials" / "_render.py"
              ).read_text(encoding="utf-8")
    assert _LIVE_RENDERER in render, (
        f"`{_LIVE_RENDERER}` n'est plus appelé par _render.py : le chemin vivant a "
        f"changé, vérifier que le sélecteur d'OS suit."
    )


def test_the_live_renderer_offers_the_os_switch():
    fn = _fn(_ST, _LIVE_RENDERER)
    assert fn is not None, f"{_LIVE_RENDERER} introuvable"
    calls = {(getattr(n.func, "id", "") or getattr(n.func, "attr", ""))
             for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "os_selector" in calls, (
        "le rendu vivant des guides n'appelle pas `os_selector()` : l'OS est deviné par "
        "User-Agent, **Windows par défaut**, sans moyen de corriger. C'est ce qu'un "
        "artiste Mac a subi le 12/08."
    )
