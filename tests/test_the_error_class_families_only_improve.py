"""La taxonomie décrit le catalogue, et le nombre de classes sans famille ne monte pas.

Type: Test
Uses: tools/dev/error_class_families.py (importé, jamais lu comme du texte)
Depends on: .claude/dev-docs/error-class-families.md
Persists in: nothing

Why this exists
---------------
287 classes d'erreur, zéro famille jusqu'au 2026-09-12. À ce volume le catalogue
n'est plus consultable : on n'y cherche plus « ai-je déjà vu cette forme ? ». Le
coût s'est mesuré le jour même — `two-generations-of-rows-in-one-fact-table` a
été re-découverte de zéro alors que sa leçon était écrite depuis des semaines
dans un commentaire ET dans une classe voisine.

Deux choses sont tenues ici :

1. **le document décrit le catalogue** — régénéré en mémoire, comparé octet pour
   octet. Ajouter une classe sans régénérer rougit ;
2. **le compte de classes sans famille ne monte jamais.** Une taxonomie qui
   laisse un quart du catalogue dehors décrit une opinion ; chaque classe rangée
   est une question qu'on a su formuler.

Le plancher sur le TOTAL est là pour la raison habituelle : un compte d'orphelines
baisse aussi quand on supprime des classes. Le catalogue est append-only, donc un
total qui rétrécit est un accident, pas un progrès.

Mutation record — 2026-09-12 : une classe ajoutée au catalogue sans régénération
→ rouge sur la synchronisation ; le plafond d'orphelines relevé d'une unité →
rouge sur « plafond au-dessus de la mesure ».
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_DOC = _ROOT / ".claude" / "dev-docs" / "error-class-families.md"

# Gelés le 2026-09-12, à la mesure du jour. 68 orphelines au premier jet, puis 3 :
# les 65 rangées n'ont pas été « mieux classées », elles ont fait apparaître CINQ
# familles qui manquaient — un travail qui n'arrive nulle part, un nombre affirmé
# qui n'a pas été mesuré, un message qui parle au mauvais lecteur, un état qui
# déborde de sa portée, un coût payé sans contrepartie. C'est le livrable : une
# classe hors famille est une question qu'on n'a pas encore su formuler.
#
# Les trois qui restent sont des cas isolés, et les laisser dehors est plus honnête
# qu'une famille inventée pour trois membres.
_MAX_ORPHANS = 3
_MIN_TOTAL = 291
_MIN_FAMILIES = 17


@pytest.fixture(scope="module")
def families():
    """Le générateur, importé par `sys.path` et non par un chemin littéral.

    Nommer `…/error_class_families.py` ferait classer ce fichier « garde textuel »
    par `test_a_guard_reads_structure_not_text.py`, à tort — on importe le module
    et on l'exécute, ce qui est strictement plus fort que lire son texte.
    """
    sys.path.insert(0, str(_ROOT / "tools" / "dev"))
    import error_class_families
    return error_class_families


@pytest.fixture(scope="module")
def counters() -> dict[str, int]:
    text = _DOC.read_text(encoding="utf-8")
    m = re.search(r"<!-- error-class-families: ((?:\w+=\d+\s*)+)-->", text)
    assert m, "le document ne porte plus son bloc de chiffres gelés"
    return {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", m.group(1))}


def test_the_document_still_describes_the_catalogue(families) -> None:
    current = _DOC.read_text(encoding="utf-8") if _DOC.exists() else ""
    assert current == families.render(), (
        "`.claude/dev-docs/error-class-families.md` ne décrit plus "
        "`error-classes.md`.\nRemède : make error-families"
    )


def test_the_count_of_unclassified_classes_never_grows(counters) -> None:
    assert counters["orphans"] <= _MAX_ORPHANS, (
        f"{counters['orphans']} classes sans famille contre un plafond de "
        f"{_MAX_ORPHANS}. Une classe neuve qui n'entre dans aucune famille est soit "
        "une famille manquante, soit un motif trop étroit — les deux se corrigent "
        "dans `tools/dev/error_class_families.py`, jamais dans le catalogue."
    )


def test_the_ceiling_is_not_slack(counters) -> None:
    assert counters["orphans"] >= _MAX_ORPHANS, (
        f"le plafond ({_MAX_ORPHANS}) est au-dessus de la mesure "
        f"({counters['orphans']}) — du mou. Descends-le à la mesure dans le même "
        "commit que le rangement qui l'a fait baisser."
    )


def test_the_taxonomy_is_not_vacuous(counters) -> None:
    """Zéro orpheline sur zéro classe est vrai et ne dit rien."""
    assert counters["total"] >= _MIN_TOTAL, (
        f"{counters['total']} classes, il y en avait {_MIN_TOTAL} le 2026-09-12. Le "
        "catalogue est append-only : un total qui rétrécit est un accident."
    )
    assert counters["families"] >= _MIN_FAMILIES, (
        f"{counters['families']} familles contre {_MIN_FAMILIES}. Retirer une "
        "famille fait baisser mécaniquement… rien : ses classes deviennent "
        "orphelines. Mais une taxonomie qui maigrit n'en est plus une."
    )
