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
from src.dashboard.utils.setup_completion import steps_from_facts


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


def _state(*, creds: bool, files, runs: int = 0):
    """Un `SetupState` depuis les faits, comme la base les rend.

    `files` est l'ensemble des types de fichiers importés ; `spotify_csv` en dérive
    exactement comme dans `read_setup_state`, sinon la mise en scène testerait une
    règle que la production n'applique pas.
    """
    files = set(files)
    return steps_from_facts(
        declared={"spotify"} if creds else set(), imported=files,
        has_mapping=False, has_playlists=False, has_pdf=False,
        has_runs=bool(runs), spotify_csv="s4a" in files)


# Les six cas d'origine, portés sur les faits que la base rend vraiment. Le cas
# « apple seul » a gagné en force le 2026-09-12 : depuis que les deux lignes d'import
# ont fusionné, l'ÉTAPE se coche sur un import Apple — et l'autostart ne doit
# toujours pas partir, puisque rien de collectable n'a été déposé. C'est exactement
# ce que la fusion risquait de casser.
@pytest.mark.parametrize("creds,files,runs,expected", [
    (True,  {"s4a", "apple"}, 0, True),    # tout fait sauf la collecte → on démarre
    (True,  {"s4a"},          0, True),    # Apple est FACULTATIF
    (True,  set(),            0, False),   # pas de CSV : le parcours n'est pas bouclé
    (True,  {"apple"},        0, False),   # un import, mais pas celui qui se collecte
    (True,  {"sacem"},        0, False),   # idem : un relevé SACEM ne collecte rien
    (False, {"s4a", "apple"}, 0, False),   # pas d'identifiant : rien à collecter
    (True,  {"s4a", "apple"}, 1, False),   # une collecte a DÉJÀ réussi → jamais deux fois
    (True,  {"s4a"},          3, False),
])
def test_the_rule_is_read_from_the_journey_itself(creds, files, runs, expected):
    """La règle, sur les faits réels — sans base, sans Streamlit."""
    assert should_autostart(_state(creds=creds, files=files, runs=runs)) is expected, (
        f"creds={creds} files={sorted(files)} runs={runs} : attendu {expected}")


def test_the_merged_csv_step_ticks_on_any_import_but_the_autostart_does_not():
    """La fusion demandée le 2026-09-12, et la limite qu'elle ne doit pas franchir.

    « Consolide les 2 lignes import csv en 1 seule » — la ligne se coche donc dès
    UN import. Faire suivre l'autostart aurait déclenché la collecte sur un relevé
    SACEM, qui ne collecte rien : la case verte aurait annoncé une collecte qui
    n'arrive jamais.
    """
    state = _state(creds=True, files={"sacem"})
    csv_step = next(s for s in state.steps if s.key == "csv")
    assert csv_step.done, "l'étape « fichiers » ne se coche plus sur un import réussi"
    assert should_autostart(state) is False, (
        "l'autostart suit maintenant l'étape fusionnée : un relevé SACEM déclenche "
        "une collecte Spotify qui n'a rien à collecter")


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
    # La CHAÎNE, pas un littéral. Le 2026-09-11, l'étape « 🚀 Lancer votre première
    # collecte » a été retirée de l'affichage — l'artiste ne lance plus rien, la
    # collecte part seule ici et repart chaque matin. Ce test cherchait la chaîne
    # `"run"` dans `should_autostart` et a donc rougi sur un changement qui préserve
    # exactement ce qu'il protège. Il vérifie désormais les DEUX bouts :
    #   1. la décision lit bien `collected` ;
    #   2. `collected` est calculé à partir du COMPTEUR DE RUNS, pas d'un drapeau.
    # Un drapeau `auto_started` en base serait une seconde source de vérité, capable
    # de dire « déjà lancé » quand aucun run n'a réussi.
    src = (_ROOT / "utils" / "collection_trigger.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "should_autostart")
    body = ast.unparse(fn)
    assert "collected" in body, (
        "`should_autostart` n'interroge plus l'état de collecte : plus rien ne "
        "l'empêche de relancer une collecte à chaque enregistrement")
    keys = {n.value for n in ast.walk(fn)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "creds" in keys, "la condition ne lit plus les identifiants"
    assert "spotify_csv" in body, (
        "la condition ne lit plus le CSV **Spotify**. Depuis la fusion des deux "
        "lignes d'import (2026-09-12), lire l'étape « fichiers » ferait partir la "
        "collecte sur un relevé SACEM.")

    setup = (_ROOT / "utils" / "setup_completion.py").read_text(encoding="utf-8")
    maker = next(n for n in ast.walk(ast.parse(setup))
                 if isinstance(n, ast.FunctionDef) and n.name == "steps_from_facts")
    assert "collected=bool(has_runs)" in ast.unparse(maker).replace(" ", ""), (
        "`collected` ne vient plus du compteur de runs — c'est devenu un drapeau, "
        "donc une seconde source de vérité qui peut affirmer « déjà lancé » alors "
        "qu'aucune collecte n'a réussi")


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


# ════════════════════════════════════════════════════════════════════════════
#  L'ARGUMENT, pas seulement l'appel
# ════════════════════════════════════════════════════════════════════════════
#
# `test_both_completing_gestures_try_to_start` ci-dessus vérifie que l'APPEL
# `autostart_if_journey_complete` existe dans l'AST. Il ne regarde pas ce qu'on lui
# passe — et c'est ainsi qu'il est resté VERT douze jours sur un parcours mort.
#
# Les deux sites passaient `from src.utils import airflow_trigger as _trigger`, donc
# le MODULE là où une INSTANCE est attendue. `trigger_all_collections` appelle
# `airflow_trigger.trigger_dag(...)` ; un module n'a pas cet attribut. Reproduit sans
# réseau le 2026-09-18 : zéro DAG lancé, chacun refusé sur
# `AttributeError: module 'src.utils.airflow_trigger' has no attribute 'trigger_dag'`.
# Dans `_render.py`, un `except Exception: pass` avalait le tout.
#
# Règle 20, dans sa forme la plus nue : le prédicat cherchait une FORME D'ÉCRITURE
# (« l'appel est là ») là où la propriété est « l'appel reçoit de quoi travailler ».

def _noms_importes_comme_modules(arbre) -> set:
    """Les noms liés par `from X import Y` où Y est un MODULE, pas un symbole.

    On ne peut pas trancher module/symbole par l'AST seul. On s'appuie donc sur la
    forme qui a produit le défaut et qui est reconnaissable : `from <paquet> import
    <nom>` où `<nom>` correspond à un fichier `.py` de ce paquet sur le disque.
    """
    from pathlib import Path

    racine = Path(__file__).resolve().parents[1]
    out = set()
    for n in ast.walk(arbre):
        if not isinstance(n, ast.ImportFrom) or not n.module:
            continue
        paquet = racine / Path(n.module.replace(".", "/"))
        if not paquet.is_dir():
            continue
        for alias in n.names:
            if any(f.stem == alias.name for f in paquet.iterdir() if f.is_file()):
                out.add(alias.asname or alias.name)
    return out


@pytest.mark.parametrize("path", _TRIGGER_SITES, ids=lambda p: p.name)
def test_the_trigger_argument_is_an_instance_not_a_module(path):
    """Ce qu'on PASSE, pas seulement qu'on appelle."""
    arbre = ast.parse(path.read_text(encoding="utf-8"))
    modules = _noms_importes_comme_modules(arbre)
    fautifs = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Call):
            continue
        if "autostart_if_journey_complete" not in ast.unparse(n.func):
            continue
        # signature : (db, artist_id, session_state, airflow_trigger, collection_dags)
        if len(n.args) < 4:
            fautifs.append(f"{path.name}: appel à {len(n.args)} argument(s)")
            continue
        arg = ast.unparse(n.args[3])
        if arg in modules:
            fautifs.append(f"{path.name}:{n.lineno} passe le MODULE `{arg}`")
    assert not fautifs, (
        "un module est passé là où une instance de déclencheur est attendue : "
        f"{fautifs}. `trigger_all_collections` appelle `trigger_dag` dessus ; un "
        "module n'a pas cet attribut, chaque DAG part dans la boucle `except` et "
        "ressort en refus poli. Passer `build_airflow_trigger()`."
    )


def test_the_module_detector_actually_separates_the_two_forms():
    """La preuve que ce fichier se donne : le détecteur doit pouvoir dire NON.

    Un détecteur qui rend l'ensemble vide laisse le test ci-dessus passer sur rien —
    exactement ce qu'a fait le prédicat précédent pendant douze jours.
    """
    modules = _noms_importes_comme_modules(
        ast.parse("from src.utils import airflow_trigger as _t\n"
                  "from src.utils.airflow_trigger import build_airflow_trigger\n"))
    assert "_t" in modules, (
        "le détecteur ne voit pas `from src.utils import airflow_trigger` comme un "
        "import de MODULE — c'est pourtant la forme exacte du défaut")
    assert "build_airflow_trigger" not in modules, (
        "le détecteur prend une FONCTION importée pour un module — il rendrait "
        "l'arbre rouge en permanence")


def test_the_seam_refuses_a_module_at_runtime():
    """La ceinture et les bretelles : même si l'AST rate un site, la couture lève.

    Un prédicat AST ne voit pas `getattr(mod, 'AirflowTrigger')()`, une fabrique
    dynamique, ni un argument passé par `**kwargs`. La couture, elle, voit ce qui
    ARRIVE.
    """
    from src.dashboard.utils.collection_trigger import trigger_all_collections
    from src.utils import airflow_trigger as module_pas_instance

    with pytest.raises(TypeError, match="au lieu d'un déclencheur"):
        trigger_all_collections(1, module_pas_instance, [("spotify_api_daily", "S")])

    # Et elle ne refuse PAS un vrai déclencheur — sinon elle bloquerait tout.
    class _Faux:
        def trigger_dag(self, dag_id, conf=None):
            return {"success": True, "dag_run_id": "x"}

    lance, refuse = trigger_all_collections(1, _Faux(), [("spotify_api_daily", "S")])
    assert lance and not refuse, (
        "la couture refuse un objet qui porte pourtant `trigger_dag` — elle est trop "
        f"stricte : {lance=} {refuse=}")
