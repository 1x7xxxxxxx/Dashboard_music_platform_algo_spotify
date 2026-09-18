"""L'effet d'un garde se mesure AVANT/APRÈS le garde, pas avec l'étiquette d'aujourd'hui.

Type: Test
Uses: tools.dev.error_class_health
Depends on: .claude/dev-docs/error-classes.md
Persists in: rien

Ce qui a été mesuré (2026-09-18)
--------------------------------
`error-class-health.json` publiait une strate `by_guard` qui étiquetait chaque classe
avec son état **d'aujourd'hui** (`guard_automatic`) et appliquait cette étiquette à
**toute sa vie** depuis `introduced_date`. Une classe née sans garde, récidivée le 5,
gardée le 6, versait ses jours ENTIERS et sa récidive dans le bras « automatique ».

Comme c'est la récidive qui fait écrire le garde, la causalité était inversée : c'est
un biais d'*immortal time*, et il gonfle l'écart dans le sens qui flatte la pratique.

Ce que valait le biais, sur le même jeu de données :

| | avec garde | sans garde | rapport |
|---|---|---|---|
| `by_guard` — étiquette d'aujourd'hui | 0,1442 | 0,7029 | **×4,9** |
| `by_guard_since` — découpé au premier garde | 0,1549 | 0,1645 | **×1,1** |

Le facteur 4,9 était **entièrement** un artefact de mesure. Et ce n'est pas anodin :
la règle 15 de `CLAUDE.md` citait ce chiffre comme la raison d'écrire un garde
automatique. Écrire un garde reste la bonne pratique ; ce jeu de données ne la démontre
pas, et une règle qui s'appuie sur une mesure doit dire quand la mesure a bougé.

Ce que ce fichier tient
-----------------------
Deux propriétés, toutes deux vérifiées sur des données FABRIQUÉES — le verdict ne doit
pas dépendre de l'état du catalogue :

1. la strate non confondue est publiée, avec son intervalle ;
2. le découpage attribue chaque évènement à la période où il s'est produit, et fait
   contribuer **la même classe aux deux bras**.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_GEN = ROOT / "tools" / "dev" / "error_class_health.py"


@pytest.fixture(scope="module")
def health():
    spec = importlib.util.spec_from_file_location("error_class_health", _GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _declared(guard_ref: str = "tests/x.py") -> dict:
    return {"classe": {
        "guard_automatic": bool(guard_ref),
        "guard_ref": guard_ref,
        "seen_red": "unknown",
        "guard_scope_has_not_covered": True,
    }}


def test_the_split_stratum_is_published_with_its_interval(health) -> None:
    """Le cliquet : la strate non confondue existe, et elle porte son IC.

    Sans elle, le document ne publie que la version confondue — et un lecteur qui
    compare deux nombres conclut à un effet qui n'est pas là.
    """
    import json
    payload = json.loads(
        (ROOT / ".claude" / "dev-docs" / "error-class-health.json").read_text("utf-8"))
    r = payload["aggregate"]["recurrence"]
    assert "by_guard_since" in r, (
        "la strate `by_guard_since` a disparu : il ne reste que `by_guard`, qui est "
        "confondu par immortal time. Le document redeviendrait une raison de croire "
        "un écart de ×4,9 qui n'existe pas.")
    for bras in ("avec-garde", "sans-garde"):
        assert bras in r["by_guard_since"], f"le bras `{bras}` n'est plus publié"
        assert r["by_guard_since"][bras].get("ci95"), (
            f"`{bras}` est publié sans intervalle. Sur 4 évènements, un point seul se "
            "lit comme un résultat — c'est exactement l'erreur que ce fichier corrige.")

    # ET LE DOCUMENT QUE LES HUMAINS LISENT, pas seulement le JSON.
    #
    # ⚠️ Mesuré en mutant : retirer `by_guard_since` de la boucle du RENDU laissait ce
    # test vert, parce qu'il ne regardait que le JSON. Le tableau qui met les deux
    # mesures côte à côte est justement la seule chose qui rende le biais visible à la
    # lecture — l'omettre laisse un lecteur comparer 0,14 à 0,70 et conclure.
    doc = (ROOT / ".claude" / "dev-docs" / "error-class-health.md").read_text("utf-8")
    # ⚠️ ON ANCRE SUR LA LIGNE DU TABLEAU, pas sur le mot.
    #
    # La version précédente cherchait `"by_guard_since" in doc` et restait VERTE quand
    # on retirait la strate du rendu : le mot survivait dans le tableau explicatif que
    # ce même correctif avait ajouté juste en dessous. `guard-satisfied-by-its-own-
    # comment`, quatrième instance de la journée — et cette fois sur ma propre prose.
    for bras in ("avec-garde", "sans-garde"):
        assert f"| by_guard_since · {bras} |" in doc, (
            f"la ligne `by_guard_since · {bras}` a disparu du tableau des strates du "
            "document rendu. Il ne reste que `by_guard`, et un lecteur y lira un "
            "écart de ×4,9 qui est un artefact de mesure.")
    assert "Ce que le biais valait" in doc, (
        "le tableau qui compare la mesure confondue à la mesure découpée a disparu. "
        "C'est lui qui empêche de citer la première ligne comme une preuve.")


def test_the_same_class_contributes_to_both_arms(health) -> None:
    """Le cœur : une classe gardée à mi-vie compte des deux côtés de sa coupure.

    Données fabriquées : une classe introduite le 1er, gardée le 11, observée jusqu'au
    21. Une récidive AVANT le garde, une APRÈS. La version confondue mettrait les deux
    dans « automatique » ; le découpage en met une de chaque côté.
    """
    observed = {
        "window_start": "2026-01-01", "as_of": "2026-01-21", "revisions": 3,
        "per_class": {"classe": {
            "introduced_date": "2026-01-01",
            "history_additions": 2,
            "guard_since": "2026-01-11",
            "recurrence_dates": ["2026-01-05", "2026-01-15"],
        }},
    }
    out = health._rates(_declared(), observed)
    split = out["by_guard_since"]

    assert split["sans-garde"]["events"] == 1, (
        f"{split['sans-garde']['events']} évènement(s) attribué(s) à la période "
        "SANS garde, contre 1 attendu. La récidive du 5 janvier est antérieure au "
        "garde du 11 : la ranger après, c'est le biais d'immortal time.")
    assert split["avec-garde"]["events"] == 1, (
        f"{split['avec-garde']['events']} évènement(s) attribué(s) à la période AVEC "
        "garde, contre 1 attendu.")
    assert split["sans-garde"]["class_days"] == 10, (
        f"{split['sans-garde']['class_days']} jours avant le garde, contre 10. "
        "L'exposition n'est pas coupée à `guard_since`.")
    assert split["avec-garde"]["class_days"] == 10, (
        f"{split['avec-garde']['class_days']} jours après le garde, contre 10.")

    # ET la moitié qui montre le biais : la strate confondue, sur les MÊMES données,
    # met tout du côté « automatique ». C'est ce que le découpage corrige.
    assert out["by_guard"]["automatique"]["events"] == 2, (
        "la strate confondue ne met plus les deux évènements du même côté — si elle a "
        "été corrigée elle aussi, ce test doit être réécrit, pas supprimé : la "
        "comparaison des deux est ce qui rend le biais visible.")


def test_a_class_that_never_had_a_guard_contributes_only_to_the_bare_arm(health) -> None:
    """L'autre extrémité : sans `guard_since`, tout va dans « sans-garde ».

    Sans cette assertion, un découpage qui rangerait TOUT dans « avec-garde » passerait
    le test précédent — il suffirait de couper au bon endroit pour la classe fabriquée.
    """
    observed = {
        "window_start": "2026-01-01", "as_of": "2026-01-21", "revisions": 2,
        "per_class": {"classe": {
            "introduced_date": "2026-01-01",
            "history_additions": 1,
            "guard_since": None,
            "recurrence_dates": ["2026-01-05"],
        }},
    }
    split = health._rates(_declared(guard_ref=""), observed)["by_guard_since"]
    assert split["sans-garde"]["events"] == 1 and split["sans-garde"]["class_days"] == 20, (
        f"une classe qui n'a JAMAIS eu de garde rend {split['sans-garde']}, alors "
        "qu'elle doit verser ses 20 jours et sa récidive dans le seul bras « sans-garde ».")
    assert split["avec-garde"]["class_days"] == 0, (
        "des jours sont comptés « avec garde » pour une classe qui n'en a jamais eu.")
