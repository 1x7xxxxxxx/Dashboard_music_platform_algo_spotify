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
    assert total <= 162, (
        f"le total des plafonds vaut {total}, contre 191 le 2026-09-20. Ce fichier "
        "descend quand une vue est allégée ; il ne monte pas. Une vue neuve doit tenir "
        f"sous {_MAX_FIRST_SCREEN} sans entrée du tout.")
