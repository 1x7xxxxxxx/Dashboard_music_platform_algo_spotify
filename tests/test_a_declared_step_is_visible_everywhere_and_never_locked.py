"""Une étape de mise en route se déclare une fois, s'affiche partout, et s'ouvre.

Type: Test
Uses: pytest, ast, src.dashboard.utils.setup_completion, src.database.stripe_schema
Depends on: src/dashboard/views/{home,onboarding,onboarding_health}.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Trois surfaces posent la même question — « où en est la mise en route ? » : le
bandeau de l'accueil, l'assistant, et la page de santé d'onboarding. Les trois
portaient leur PROPRE liste d'étapes, donc ajouter la saisie S4A le 2026-09-12
demandait trois éditions et deux d'entre elles ont divergé au moins une fois dans
l'histoire de ce module (son propre docstring le raconte pour `_STEP_PAGES` et
`STEP_LABELS`).

Et une étape peut être visible et malgré tout infaisable. C'est arrivé deux fois :
« Lancer votre première collecte » pointait vers `trigger_algo`, page Premium — un
artiste Free cliquait et atterrissait sur le paywall depuis son propre parcours de
mise en route ; l'étape a été supprimée. Le 2026-09-12, `pdf` la rejouait à
l'identique, `export_pdf` étant passé Premium le 2026-09-04.

Les deux sens du garde
----------------------
1. **Visibilité** — chacune des trois vues lit le registre (`read_setup_state`) et
   en dérive son libellé (`STEP_LABELS[...]`). Lu en AST : une vue qui reviendrait
   à sa propre liste perdrait l'un des deux et le test le nommerait.
2. **Atteignabilité** — aucune étape DÉCLARÉE ne pointe vers une page fermée au
   plan gratuit, hors la liste explicite `_PREMIUM_ONLY_STEPS`. Le prédicat est
   `page_is_locked`, celui du menu : deux copies divergeraient.

   ⚠️ Ce sens-là a été écrit deux fois. La première version interrogeait la sortie
   FILTRÉE de `steps_from_facts(plan=…)` — elle ne pouvait pas rougir, puisque le
   filtre est précisément ce qui retire les étapes verrouillées. Muté, il est resté
   vert sur le défaut : verrouiller la saisie S4A la faisait simplement DISPARAÎTRE
   de la liste du plan gratuit, ce qui est exactement le dégât qu'on veut voir.
   On lit donc la DÉCLARATION, et le filtre est tenu à part par le cas 1 bis.

Non-vacuité : le troisième cas épingle la RÉALITÉ — la saisie S4A est déclarée et
ouverte au plan gratuit — pour qu'assouplir la règle ne suffise pas à rendre ce
fichier vert.

Journal de mutation — 2026-09-12 :
  * `saisie_s4a` retirée de `_FREE_FEATURES` → le cas 2 rougit en nommant
    `playlists → saisie_s4a`, ET le cas de non-vacuité rougit à son tour ;
  * `STEP_LABELS[...]` remplacé par une liste littérale dans `onboarding.py` → le
    cas 1 rougit en nommant le fichier et ce qui lui manque.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_VIEWS = _ROOT / "src" / "dashboard" / "views"

# Les trois surfaces, et la fonction qui y porte la lecture. Le nom de fonction
# n'est PAS vérifié : ce qui compte est que le module lise le registre, pas où.
_SURFACES = ("home.py", "onboarding.py", "onboarding_health.py")


def _tree(name: str) -> ast.Module:
    path = _VIEWS / name
    assert path.exists(), f"{name} a disparu de views/ — la surface n'existe plus ?"
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _calls_named(tree: ast.Module, func: str) -> int:
    return sum(1 for n in ast.walk(tree)
               if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Name) and n.func.id == func)


def _subscripts_of(tree: ast.Module, name: str) -> int:
    return sum(1 for n in ast.walk(tree)
               if isinstance(n, ast.Subscript)
               and isinstance(n.value, ast.Name) and n.value.id == name)


@pytest.mark.parametrize("module", _SURFACES)
def test_every_surface_reads_the_declaration_instead_of_its_own_list(module):
    """Une même question, une seule liste — sinon ajouter une étape en oublie deux."""
    tree = _tree(module)
    reads = _calls_named(tree, "read_setup_state")
    labels = _subscripts_of(tree, "STEP_LABELS")
    assert reads >= 1 and labels >= 1, (
        f"{module} ne lit plus le registre des étapes "
        f"(read_setup_state : {reads} appel(s), STEP_LABELS[...] : {labels} "
        f"lecture(s)). Une surface qui porte sa propre liste d'étapes diverge au "
        f"premier ajout — c'est ce que `setup_completion` raconte déjà pour "
        f"`_STEP_PAGES` et `STEP_LABELS`.")


# Les étapes dont on ASSUME qu'un compte gratuit ne les verra pas. La liste est
# courte et elle doit le rester : chaque entrée est une étape de mise en route que
# le plan gratuit ne fera jamais. `pdf` y est depuis le 2026-09-04 par une décision
# de prix écrite dans `stripe_schema.py` — « la sortie brute reste gratuite, la mise
# en forme est le service ». Y ajouter une clé est un geste délibéré, et c'est le
# but : on ne ferme pas une étape de mise en route par accident.
_PREMIUM_ONLY_STEPS = {"pdf"}


def test_no_declared_step_is_locked_for_a_free_account():
    """Une étape ne mène JAMAIS à un mur de paiement — lu sur la DÉCLARATION.

    Pas sur la sortie filtrée : le filtre retire les étapes verrouillées, donc un
    test qui l'interroge ne peut pas rougir. Mesuré par mutation le 2026-09-12.
    """
    from src.database.stripe_schema import page_is_locked
    from src.dashboard.utils.setup_completion import _STEPS

    faults = [f"{d.key} → {d.page}" for d in _STEPS
              if d.key not in _PREMIUM_ONLY_STEPS and page_is_locked("free", d.page)]
    assert not faults, (
        "des étapes de mise en route mènent à une page verrouillée pour un compte "
        "gratuit : " + " · ".join(faults)
        + ". Deux fois déjà : `trigger_algo` (étape supprimée), puis `export_pdf` "
          "(déclarée Premium ici). Soit la page s'ouvre, soit l'étape est inscrite "
          "dans `_PREMIUM_ONLY_STEPS` en connaissance de cause — elle disparaîtra "
          "alors du parcours gratuit, ce qui n'est pas neutre.")


def test_the_plan_filter_hides_exactly_the_premium_only_steps():
    """1 bis — le filtre fait ce que le cas ci-dessus suppose, et rien de plus."""
    from src.dashboard.utils.setup_completion import _STEPS, steps_from_facts

    facts = dict(declared=set(), imported=set(), has_mapping=False,
                 has_playlists=False, has_pdf=False)
    free = {s.key for s in steps_from_facts(plan="free", **facts).steps}
    every = {d.key for d in _STEPS}
    assert free == every - _PREMIUM_ONLY_STEPS, (
        f"le filtre par plan ne retire pas ce qu'on croit : un compte gratuit voit "
        f"{sorted(free)}, on attendait {sorted(every - _PREMIUM_ONLY_STEPS)}. "
        f"Un filtre trop large ampute le parcours en silence ; trop étroit, il "
        f"ramène le paywall.")
    assert {d.key for d in _STEPS} == {
        s.key for s in steps_from_facts(plan=None, **facts).steps}, (
        "`plan=None` doit rendre la déclaration ENTIÈRE — c'est ce que lisent les "
        "appelants qui ne connaissent pas le plan (un DAG, un test pur).")


def test_the_s4a_entry_step_exists_and_is_free():
    """NON-VACUITÉ : sans ce sens, tout assouplir rendrait le fichier vert.

    C'est la demande du 2026-09-12 — « rajoute dans mise en route + santé
    onboarding l'action de saisir mes ajouts en playlist S4A » — épinglée comme un
    FAIT, pas comme une constante relue.
    """
    from src.database.stripe_schema import page_is_locked
    from src.dashboard.utils.setup_completion import STEP_HINTS, steps_from_facts

    state = steps_from_facts(plan="free", declared=set(), imported=set(),
                             has_mapping=False, has_playlists=False, has_pdf=False)
    step = next((s for s in state.steps if s.key == "playlists"), None)
    assert step is not None, (
        "l'étape « saisir mes ajouts en playlist (S4A) » a disparu du registre — "
        "les trois surfaces cessent de la montrer du même coup")
    assert step.page == "saisie_s4a", f"elle pointe vers {step.page}"
    assert not page_is_locked("free", step.page), (
        "la saisie S4A est redevenue Premium. Elle nourrit les modèles "
        "prédictifs : la brider punit surtout la précision des prédictions.")
    assert "playlists" in STEP_HINTS, (
        "l'étape a perdu son `hint`. C'est la seule dont le bénéfice n'est pas "
        "devinable depuis le geste, et une étape dont on ne voit pas le gain est "
        "une étape qu'on saute.")
