"""Guard: finishing the setup starts the collection — nobody has to find a button.

Type: Utility
Uses: ast, src.dashboard.utils.collection_trigger
Triggers: pytest
Persists in: nothing

Error class `journey-completes-and-nothing-happens`.

The setup has four steps. Three are the artist's (identifiers, S4A CSV, Apple CSV);
the fourth — "a collection succeeded" — is the machine's. Nothing fired it: the
artist had to find, in the sidebar, a panel that never presented itself as the next
thing to do. Two beta sessions ended on a complete configuration and zero data.

The whole design rests on one decision, and that is what this file guards:
**idempotence is DERIVED, not stored**. We start only when `etl_run_log` holds no
successful run for this tenant — the very counter the journey already uses for its
fourth step. No migration, no second source of truth that could drift from the runs
themselves, and no way to loop.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.utils.collection_trigger import should_autostart
from src.dashboard.utils.setup_completion import steps_from_counts


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


_ROOT = _repo_root() / "src" / "dashboard"
# Les deux gestes qui peuvent BOUCLER le parcours. Les deux doivent déclencher :
# n'en câbler qu'un laisse la moitié des artistes devant une étape ⬜.
_TRIGGER_SITES = (
    _ROOT / "views" / "upload_csv.py",
    _ROOT / "views" / "credentials" / "_render.py",
)


@pytest.mark.parametrize("creds,csv,apple,runs,expected", [
    (1, 1, 1, 0, True),    # tout fait sauf la collecte → on démarre
    (1, 1, 0, 0, True),    # Apple est FACULTATIF : beaucoup n'ont pas de compte
    (1, 0, 0, 0, False),   # pas de CSV S4A : le parcours n'est pas bouclé
    (0, 1, 1, 0, False),   # pas d'identifiant : rien à collecter
    (1, 1, 1, 1, False),   # une collecte a DÉJÀ réussi → jamais deux fois
    (1, 1, 0, 3, False),
])
def test_the_rule_is_read_from_the_journey_itself(creds, csv, apple, runs, expected):
    """La règle, sur les quatre compteurs réels — sans base, sans Streamlit."""
    state = steps_from_counts(creds, csv, apple, runs)
    assert should_autostart(state) is expected, (
        f"creds={creds} csv={csv} apple={apple} runs={runs} : "
        f"attendu {expected}")


def test_an_unreadable_state_never_starts_anything():
    """`read_setup_state` rend AUCUNE étape quand la lecture échoue.

    Traiter ce cas comme « parcours bouclé » déclencherait une collecte sur une base
    qu'on ne sait pas lire — exactement quand il ne faut rien faire.
    """
    from src.dashboard.utils.setup_completion import SetupState
    assert should_autostart(SetupState(steps=[], show_on_login=True)) is False


def test_the_idempotence_is_derived_from_the_runs_not_from_a_flag():
    """La décision de conception, gardée parce qu'elle est facile à « simplifier ».

    Un drapeau `auto_started` en base serait une SECONDE source de vérité : il peut
    dire « déjà lancé » alors qu'aucun run n'a réussi, et l'artiste resterait sans
    données avec une étape cochée. Le compteur des runs ne peut pas mentir là-dessus.
    """
    src = (_ROOT / "utils" / "collection_trigger.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "should_autostart")
    keys = {n.value for n in ast.walk(fn)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "run" in keys, (
        "`should_autostart` n'interroge plus l'étape `run` : plus rien ne l'empêche "
        "de relancer une collecte à chaque enregistrement")
    assert "creds" in keys and "s4a" in keys, (
        "la condition ne lit plus les étapes de l'artiste")


@pytest.mark.parametrize("path", _TRIGGER_SITES, ids=lambda p: p.name)
def test_both_completing_gestures_try_to_start(path):
    """Identifiants ET import CSV. L'un des deux seulement laisse la moitié en rade."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    called = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert any("autostart_if_journey_complete" in c for c in called), (
        f"{path.name} ne tente pas de démarrer la collecte — un artiste qui boucle "
        "son parcours par CE geste-là reste devant une quatrième étape ⬜")


def test_the_verdict_survives_the_rerun_that_follows_the_save():
    """`_handle_save` finit par `st.rerun()`, qui efface l'écran.

    Un `st.success` posé au point de déclenchement n'est lu par personne — c'est le
    défaut exact qui avait rendu invisible le verdict de sauvegarde. Le résultat
    passe donc par la session, et quelqu'un doit le relire.
    """
    # Par AST, et j'ai écrit la version textuelle d'abord : le cliquet
    # `test_a_guard_reads_structure_not_text` l'a prise. Il a raison — ce fichier
    # NOMME `AUTOSTART_KEY` dans sa propre docstring, donc une recherche de chaîne
    # resterait verte le jour où l'écriture disparaîtrait et où seule la prose
    # resterait.
    def _names(path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}

    render_names = _names(_ROOT / "views" / "credentials" / "_render.py")
    router_names = _names(_ROOT / "views" / "credentials" / "router.py")
    assert "AUTOSTART_KEY" in render_names, (
        "le résultat du démarrage n'est plus porté par la session")
    assert "AUTOSTART_KEY" in router_names, (
        "personne ne relit le résultat du démarrage après le rerun : le message est "
        "écrit puis effacé, comme le verdict de sauvegarde avant sa correction")
