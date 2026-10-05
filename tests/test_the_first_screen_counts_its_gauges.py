"""Le premier écran compte aussi ses JAUGES, et son plafond ne peut que descendre.

Type: Test
Uses: ast
Depends on: src/dashboard/views/**, .claude/dev-docs/first-screen-ceilings.json
Persists in: nothing

Pourquoi ce garde existe
------------------------
`test_a_view_opens_on_one_decision` plafonne le premier écran à **5 figures** et rend
**0 fichier en faute** — mais son `_RENDERERS` **n'inclut pas `st.metric`**, alors que la
`root_cause` de la classe compte les jauges. En les comptant, mesuré le 2026-09-20
(R140 §16.17) : **17 fichiers dépassent, pour 191 figures**.

    34  revenue_forecast.py        (5 sans les jauges)
    19  airflow_kpi.py             (3)
    19  data_wrapped.py            (5)
    19  meta_ads_overview.py       (5)
    12  admin.py                   (1)

⚠️ **Ce garde n'est PAS une barrière, et c'est délibéré.** Faire rougir 17 fichiers d'un
coup est le meilleur moyen de faire désactiver un garde — c'est exactement le verdict que
`code-critic` a rendu sur R133 (« 28 est un PLAFOND, ne pas migrer d'un coup »). Les 17
sont donc enregistrés, chacun à SA valeur, et le fichier de plafonds ne peut que
rétrécir. Une vue NEUVE, elle, doit tenir sous 5 sans entrée du tout.

⚠️ **`st.tabs` BORNE un écran** — décision du 2026-09-20. Un onglet n'est pas du premier
écran, donc le comptage reste PAR FICHIER et les modules `_tab_*` sont comptés
séparément. C'est ce qui rend `trigger_algo` défendable : 1 à 4 figures par onglet. La
question avait été posée en sens inverse dans R140 §16.17 (« par sa propre définition, un
onglet est du premier écran ») ; la trancher ainsi est un choix, écrit pour être contredit.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_a_view_opens_on_one_decision import (  # noqa: E402
    _MAX_FIRST_SCREEN, _RENDERERS, _collapsed_lines, _view_files,
)

_PLAFONDS = ROOT / ".claude" / "dev-docs" / "first-screen-ceilings.json"
_AVEC_JAUGES = _RENDERERS | {"metric"}


def _compte(rel: str) -> int:
    """Les figures du premier écran de ce fichier, JAUGES COMPRISES."""
    arbre = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    caches = _collapsed_lines(arbre)
    return sum(1 for n in ast.walk(arbre)
               if isinstance(n, ast.Call)
               and (getattr(n.func, "attr", "") or getattr(n.func, "id", ""))
               in _AVEC_JAUGES
               and n.lineno not in caches)


def _reference() -> dict:
    return json.loads(_PLAFONDS.read_text(encoding="utf-8"))


def test_the_gauge_renderer_is_actually_counted() -> None:
    """ANTI-VACUITÉ : sans `metric`, ce fichier mesure la même chose que son voisin."""
    assert "metric" in _AVEC_JAUGES and "metric" not in _RENDERERS, (
        "`metric` est passé dans `_RENDERERS` du garde dur — ce fichier ne mesure plus "
        "rien de neuf, et 17 fichiers sont soudain en faute chez le voisin.")


def test_the_ceiling_file_names_real_files() -> None:
    """Un plafond sur un fichier disparu est une exemption qui ne garde rien."""
    ref = _reference()["plafonds"]
    fantomes = [rel for rel in ref if not (ROOT / rel).is_file()]
    assert not fantomes, (
        f"plafond(s) sur un fichier absent : {fantomes}. Le retirer du JSON — une "
        "entrée qui ne désigne rien fait croire que le compte est suivi.")


def test_no_view_exceeds_its_recorded_ceiling() -> None:
    """LE CLIQUET. Chaque vue peut descendre, aucune ne peut monter."""
    ref = _reference()["plafonds"]
    montees = []
    for rel in _view_files():
        n = _compte(rel)
        plafond = ref.get(rel, _MAX_FIRST_SCREEN)
        if n > plafond:
            montees.append(f"{rel} : {n} figures (plafond {plafond})")
    assert not montees, (
        "vue(s) ayant gagné des figures de premier écran :\n  " + "\n  ".join(montees) +
        f"\n\nLe plafond par défaut est {_MAX_FIRST_SCREEN} — Few, *Information "
        "Dashboard Design* : un tableau de bord tient dans un coup d'œil. Les jauges "
        "comptent : elles occupent le même écran et demandent la même attention.\n"
        "Replier sous `secondary_analyses(...)` ou `st.expander(...)`, ou déplacer dans "
        "un onglet — un onglet BORNE un écran.")


def test_the_ceilings_only_fall() -> None:
    """Le total enregistré est un plafond global : 191 → 162 le 2026-09-21.

    La baisse vient de cinq resserrages (des sections supprimées ce jour-là),
    entrée neuve de `meta_x_spotify` (7) COMPRISE. Le détail est dans
    `_note_2026_09_21` du fichier de plafonds, à côté des nombres qu'il explique.

    ⚠️ Le chiffre est celui que la mesure a rendu, pas celui que j'avais estimé :
    mon premier jet annonçait 169 en additionnant à la main, et le total réel est
    162. Écrire une somme sans la relire est exactement ce que ce cliquet existe
    pour attraper ailleurs.
    """
    total = sum(_reference()["plafonds"].values())
    # 113 → 119 le 2026-10-05 (R383, V37 demandé par le propriétaire) : apple_music
    # entre à 6 — les Shazams du Top 10 deviennent un graphique ; aucune vue n'avait de marge.
    assert total <= 119, (  # 162 → 113 le 2026-10-05 (R371, `_note_2026_10_05`)
        f"le total des plafonds vaut {total}, contre 191 le 2026-09-20. Ce fichier "
        "descend quand une vue est allégée ; il ne monte pas. Une vue neuve doit tenir "
        f"sous {_MAX_FIRST_SCREEN} sans entrée du tout.")


# ── Le MULTIPLICATEUR de boucle : un site, N figures (2026-09-26) ─────────────────
#
# Tout ce qui précède compte des SITES d'appel. Le 2026-09-26, la capture du dossier
# des graphiques (R203, instantané artiste 1) a rendu **44 figures** sur ml_performance,
# dont **38** venues d'UNE ligne — `st.plotly_chart` dans `ml_widgets._render_one_gauge`,
# appelé une fois par entrée des registres `ALGO_FEATURE_ZONES` / `ALGO_VOLUME_ZONES`.
# Ce fichier voyait 0 : le site vivait dans `utils/`, et il était dans une BOUCLE. Un
# compte d'AST prouve qu'une arête est DESSINÉE, pas combien de fois elle TIRE.
#
# Le garde d'exécution est `test_a_helper_does_not_draw_one_figure_per_registry_entry`.
# Celui-ci est l'angle mort STATIQUE de la classe : il signale un dessin (un renderer,
# ou une fonction de `utils/` qui en atteint un) sous un `for` dont l'itérable n'est pas
# BORNÉ PAR CONSTRUCTION. La propriété est « littéral contre registre/base », jamais un
# nombre d'éléments : un littéral de 6 (`_PLATFORMS`) est borné, `ak.populated_algos()`
# rend 3 aujourd'hui et ne l'est pas — c'est exactement ce qui a produit les 38.
#
# Cliquet, pas barrière : les sites vivants au 2026-09-26 sont enregistrés un par un, avec
# leur raison, et une entrée qui cesse de signaler doit sortir de la liste.

_UTILS = ROOT / "src" / "dashboard" / "utils"
_BOUCLE_LITTERALE = (ast.Tuple, ast.List, ast.Set, ast.Dict)
_ENVELOPPES = {"enumerate", "sorted", "reversed"}

#: Mesuré le 2026-09-26 par `_multiplicateurs()` sur views/** et utils/** : 7 sites.
#: Clé `fichier::fonction` — stable quand des lignes bougent au-dessus.
_BOUCLES_CONNUES: dict[str, str] = {
    "src/dashboard/utils/platform_chart_notes.py::_render_recap":
        "st.metric par ligne de récapitulatif, par rangées de 4 — suit le nombre de lignes",
    "src/dashboard/views/airflow_kpi.py::_render_insertion_test":
        "une rangée de st.metric par DAG testé — 16 jauges au balayage du 2026-09-18",
    "src/dashboard/views/meta_cpr_optimizer.py::_render_detail_cards":
        "3 st.metric par campagne (`df.iterrows()`) — suit le nombre de campagnes",
    "src/dashboard/views/ml_performance.py::_show_scorecard_tab":
        "ak.populated_algos() × render_classification_scorecard (5 metric + 1 matrice) — "
        "MÊME forme que le défaut des 38 jauges ; borné à 3 par le registre, pas par le code",
    "src/dashboard/views/trigger_algo/_tab_model.py::_show_tab_model":
        "ak.populated_algos() × render_classification_scorecard(compact) — même forme",
    "src/dashboard/views/trigger_algo/_tab_explainability.py::_show_tab_explainability":
        "ak.populated_algos() × render_lever_sensitivity (DW seul, par un `if`) — c'est "
        "la boucle qui appelait les 38 jauges ; les tables ne sont plus des figures",
}


def _nom(appel: ast.Call) -> str:
    return getattr(appel.func, "attr", "") or getattr(appel.func, "id", "")


def _qui_dessine(arbres: list[ast.Module]) -> set[str]:
    """Les fonctions (par nom) qui atteignent un renderer, par point fixe sur leurs appels."""
    corps: dict[str, list[set[str]]] = {}
    for arbre in arbres:
        for n in ast.walk(arbre):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                corps.setdefault(n.name, []).append(
                    {_nom(c) for c in ast.walk(n) if isinstance(c, ast.Call)})
    atteint: set[str] = set()
    bouge = True
    while bouge:
        bouge = False
        for nom, appels in corps.items():
            if nom not in atteint and any(a & (_AVEC_JAUGES | atteint) for a in appels):
                atteint.add(nom)
                bouge = True
    return atteint


def _bornes(arbre: ast.Module) -> set[str]:
    """Noms bornés par construction : un littéral de module, ou `st.columns(<littéral>)`."""
    out: set[str] = set()
    for n in arbre.body:
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and isinstance(n.value, _BOUCLE_LITTERALE):
            cibles = n.targets if isinstance(n, ast.Assign) else [n.target]
            out |= {c.id for c in cibles if isinstance(c, ast.Name)}
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                and _nom(n.value) == "columns" and n.value.args
                and isinstance(n.value.args[0], (ast.Constant, ast.List))):
            out |= {c.id for c in n.targets if isinstance(c, ast.Name)}
    return out


def _borne(it: ast.expr, bornes: set[str]) -> bool:
    if isinstance(it, _BOUCLE_LITTERALE):
        return True
    if isinstance(it, ast.Name):
        return it.id in bornes
    if isinstance(it, ast.Subscript):
        return _borne(it.value, bornes)
    if isinstance(it, ast.Call) and getattr(it.func, "id", "") == "zip":
        return any(_borne(a, bornes) for a in it.args)  # zip s'arrête au PLUS COURT
    if isinstance(it, ast.Call) and getattr(it.func, "id", "") in _ENVELOPPES:
        return bool(it.args) and all(_borne(a, bornes) for a in it.args)
    if (isinstance(it, ast.Call) and _nom(it) in {"items", "keys", "values"}
            and isinstance(it.func.value, ast.Name)):
        return it.func.value.id in bornes
    return False


def _boucles_qui_dessinent(arbre: ast.Module, dessinent: set[str]) -> list[tuple[str, int]]:
    """[(fonction englobante, ligne du for)] — un dessin sous un itérable non borné."""
    bornes = _bornes(arbre)
    fonctions = [n for n in ast.walk(arbre)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    out = []
    for boucle in ast.walk(arbre):
        if not isinstance(boucle, (ast.For, ast.AsyncFor)) or _borne(boucle.iter, bornes):
            continue
        if any(isinstance(c, ast.Call) and _nom(c) in (_AVEC_JAUGES | dessinent)
               for s in boucle.body for c in ast.walk(s)):
            englobe = [f.name for f in fonctions
                       if f.lineno <= boucle.lineno <= (f.end_lineno or f.lineno)]
            out.append((englobe[-1] if englobe else "<module>", boucle.lineno))
    return out


def _multiplicateurs() -> set[str]:
    utils = sorted(p for p in _UTILS.rglob("*.py") if "__pycache__" not in str(p))
    dessinent = _qui_dessine([ast.parse(p.read_text(encoding="utf-8")) for p in utils])
    fichiers = [ROOT / rel for rel in _view_files()] + utils
    out = set()
    for p in fichiers:
        rel = str(p.relative_to(ROOT))
        for fn, _ligne in _boucles_qui_dessinent(ast.parse(p.read_text(encoding="utf-8")),
                                                 dessinent):
            out.add(f"{rel}::{fn}")
    return out


def _signale(source: str, utils_source: str = "") -> list[tuple[str, int]]:
    dessinent = _qui_dessine([ast.parse(utils_source)]) if utils_source else set()
    return _boucles_qui_dessinent(ast.parse(source), dessinent)


def test_the_loop_detector_sees_the_defect_it_is_written_for() -> None:
    """Les deux sens, sur des fixtures — un prédicat jamais vu rouge ne garde rien."""
    # Faux NÉGATIF à éviter : le défaut, écrit directement…
    assert _signale("def f(algo):\n    for fid in ak.feature_ids(algo):\n"
                    "        st.plotly_chart(fig)\n") == [("f", 2)]
    # …et à travers un assistant de utils/ (la forme réelle des 38 jauges).
    utils = "def _one(spec):\n    st.plotly_chart(fig(spec))\n" \
            "def gauges(algo):\n    _one(algo)\n"
    assert _signale("def show():\n    for a in ak.populated_algos():\n        gauges(a)\n",
                    utils) == [("show", 2)]
    # Faux POSITIFS à éviter : un littéral borne, QUEL QUE SOIT son nombre d'éléments.
    assert _signale("def f():\n    for algo in ('DW', 'RR', 'RADIO'):\n"
                    "        st.plotly_chart(fig)\n") == []
    six = "_PLATFORMS = [('a', 1), ('b', 2), ('c', 3), ('d', 4), ('e', 5), ('f', 6)]\n"
    assert _signale(six + "def f():\n    cols = st.columns(len(_PLATFORMS))\n"
                    "    for col, (k, _) in zip(cols, _PLATFORMS):\n"
                    "        col.metric(k, 1)\n") == []
    assert _signale(six + "def f():\n    for k, _ in _PLATFORMS:\n"
                    "        st.metric(k, 1)\n") == []
    # Et une boucle non bornée qui ne DESSINE pas n'est pas signalée.
    assert _signale("def f(rows):\n    for r in rows:\n        st.dataframe(r)\n") == []


def test_no_new_loop_multiplies_figures() -> None:
    """LE CLIQUET. Une boucle neuve qui dessine sous un itérable non borné rougit."""
    neufs = sorted(_multiplicateurs() - set(_BOUCLES_CONNUES))
    assert not neufs, (
        "boucle(s) qui dessinent une figure PAR ÉLÉMENT d'un itérable non borné :\n  "
        + "\n  ".join(neufs) +
        "\n\nUn site d'appel dans une boucle sur un registre ou une requête compte 1 pour "
        "les gardes de premier écran et dessine N figures — 38 sur ml_performance le "
        "2026-09-26. Mettre les éléments dans UN st.dataframe, ou itérer sur un littéral.")


def test_every_known_loop_still_needs_its_entry() -> None:
    """Une exemption se vérifie : une entrée qui ne signale plus rien doit sortir."""
    perimes = sorted(set(_BOUCLES_CONNUES) - _multiplicateurs())
    assert not perimes, (
        f"entrée(s) de `_BOUCLES_CONNUES` qui ne signalent plus rien : {perimes}. Les "
        "retirer — une exemption laissée derrière masquerait le retour du défaut.")
