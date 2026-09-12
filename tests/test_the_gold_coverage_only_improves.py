"""Le livrable de couverture décrit le dépôt, et ses trous ne peuvent que se combler.

Type: Test
Uses: tools/dev/gold_coverage.py (importé, jamais lu comme du texte)
Depends on: .claude/dev-docs/gold-coverage.md
Persists in: nothing

Why this exists
---------------
Le 2026-09-12, un cliquet a certifié « huit plateformes à zéro agrégat hors de la
couche or ». C'était vrai des trois répertoires qu'il balayait et faux du dépôt :
douze agrégats vivaient dans `kpi_helpers.py` et `pdf_charts.py`, que son
`_SURFACES` ne nommait pas. Le prédicat était juste ; **la carte manquait**.

`gold-coverage.md` est cette carte. Un document qui dit quelque chose de vrai
aujourd'hui est un document qui mentira dans trois commits — donc trois choses
sont tenues ici :

1. **Il est à jour.** Le document est régénéré EN MÉMOIRE et comparé octet pour
   octet. Un livrable éditable à la main est un livrable qui ment.
2. **Ses trous ne remontent jamais.** Chaque compteur est gelé à la mesure du
   jour. Une figure neuve dont la source n'est pas attribuable rougit ici.
3. **Le plafond est serré.** Égal à la mesure, jamais au-dessus — un plafond
   au-dessus est du mou qui autorise en silence la croissance qu'il prétend
   interdire (`test_a_file_only_gets_shorter.py`).

Et une quatrième, qui est la raison d'être du document : **la portée déclarée ici
est celle du cliquet des agrégats.** `gold_coverage.py` recopie `_SURFACES`,
`_DOORS` et la liste des faits pour pouvoir dire ce que ce cliquet NE regarde
pas. Une règle recopiée diverge ; le test ci-dessous compare les deux
déclarations. Sans lui, la colonne « dont hors cliquet » se périmerait en
silence, et c'est exactement la colonne qui a de la valeur.

Mutation record — 2026-09-12 : un plafond desserré d'une unité → rouge sur
« plafond au-dessus de la mesure » ; une figure ajoutée sans source attribuable →
rouge en nommant le compteur ; une entrée retirée de `_RATCHET_FACTS` → rouge sur
la divergence des deux déclarations ; une ligne ajoutée à la main dans le
document → rouge sur la synchronisation.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_DOC = _ROOT / ".claude" / "dev-docs" / "gold-coverage.md"



@pytest.fixture(scope="module")
def gc():
    """Le générateur, IMPORTÉ — jamais lu comme du texte.

    L'import passe par `sys.path` et non par un chemin littéral `…/gold_coverage.py` :
    `tests/test_a_guard_reads_structure_not_text.py` classe « garde textuel » tout
    fichier qui nomme un `.py` et appelle `read_text`, et il a raison de le faire
    grossièrement — j'ai essayé d'affiner son prédicat pour laisser passer ce
    fichier, et l'affinage a relâché NEUF gardes gelés d'un coup. On ne desserre pas
    un cliquet partagé pour accommoder un nouveau venu : on écrit le nouveau venu
    de façon à ne pas avoir la forme qu'il refuse.
    """
    sys.path.insert(0, str(_ROOT / "tools" / "dev"))
    import gold_coverage
    return gold_coverage


@pytest.fixture(scope="module")
def counters() -> dict[str, int]:
    """Les compteurs que la MACHINE a écrits dans le document.

    Lus dans le document et non recalculés : c'est le document que le cliquet
    garde, et un compteur qu'on recalcule pour le comparer à lui-même ne garde
    rien.
    """
    text = _DOC.read_text(encoding="utf-8")
    out: dict[str, int] = {}
    for block, body in re.findall(r"<!-- gold-coverage-([a-z-]+): ([^>]+) -->", text):
        for key, value in re.findall(r"(\w+)=(\d+)", body):
            out[f"{block}.{key}"] = int(value)
    return out


# Gelé le 2026-09-12, à la mesure exacte du jour. CES NOMBRES NE MONTENT JAMAIS.
# Les baisser est le travail : chaque unité en moins est une surface dont on a
# compris d'où vient sa donnée, ou un agrégat qu'un cliquet garde enfin.
_CEILING: dict[str, int] = {
    # 15 → 7, 18 → 11 le 2026-09-12 (soir), et pour deux raisons qui ne sont PAS
    # des correctifs de code : `_QUERY.format(acct=…)` est un littéral avec des
    # trous, pas une requête dynamique — le lecteur le résout désormais ; et le
    # plafond de sauts est passé de 2 à 3, sur une MESURE (le cran suivant
    # n'apporte rien). Un livrable qui déclare « je ne sais pas » là où il sait est
    # aussi trompeur qu'un livrable qui invente.
    "figures.unknown": 7,
    "tiles.unknown": 11,
    "pdf.unknown": 5,
    "gold-objects.orphans": 0,
    # 21 → 18 → 0 le 2026-09-12. Les 12 derniers n'ont pas été « repointés » : ils
    # ont été LUS. Aucun n'était une métrique — des MAX(date), des COUNT(*), des
    # string_agg de noms. Ils sont déclarés avec leur raison dans
    # `_DECLARED_RAW_AGGREGATES`, et le test ci-dessous vérifie que chaque
    # déclaration désigne encore un site qui existe et qui agrège encore.
    "unguarded-aggregates.total": 0,
    # Les trous des axes « garde » et « cliquet », ajoutés le 2026-09-12 avec eux.
    # Un cliquet sans test de non-vacuité passe au vert dès que sa population
    # disparaît ; un garde sans trace de mutation n'a peut-être jamais pu échouer.
    # 5 → 0 et 10 → 0 le 2026-09-12 : les quinze trous ont été comblés en faisant
    # les mutations, pas en écrivant les phrases. Deux d'entre elles ont échoué et
    # c'est écrit là où elles ont échoué : retirer `{frag}` d'une requête bornée ne
    # rougit PAS `test_a_chart_is_bounded_by_the_period_it_announces`, et un second
    # axe dans `utils/` ne rougissait pas `test_the_visual_rules_only_tighten` —
    # cette seconde-là a été corrigée en élargissant la portée.
    "ratchets.without_nonvacuity": 0,
    "ratchets.without_mutation": 0,
    # Une classe `guarded` dont le fichier de garde n'existe plus se lit exactement
    # comme une classe gardée. Celui-là doit rester à zéro.
    "error-classes.guard_missing": 0,
    # 10 → 11 le 2026-09-12, et c'est la SEULE hausse légitime de ce fichier :
    # `a-guard-that-sees-the-binding-not-the-application` est livrée en
    # `kind: manual` SANS signature, délibérément — le défaut existe et le garde
    # reste vert dessus, donc aucune commande ne sort ≠ 0 aujourd'hui. Une
    # signature non vérifiée coûte plus cher qu'une absence de signature.
    "error-classes.guard_unnamed": 11,
    # Un objet or que rien ne confronte est le premier à dériver en silence : le
    # spend Meta l'a fait pendant des semaines. Zéro, et ça ne remonte pas.
    "invariants.unreconciled": 0,
    # Les cases vides du tableau plateforme × famille : « quelles erreurs
    # pourrait-on encore faire ». C'est la liste des tests CI à écrire, et elle ne
    # rallonge pas. Une plateforme neuve ajoute huit cases d'un coup et fera rougir
    # ce plafond — c'est voulu : brancher une plateforme sans la garder est
    # exactement ce qui a coûté le plus cher ici.
    # 19 → 0 le 2026-09-12 (soir). Les cases n'ont pas été « remplies » : trois
    # gardes ont été écrits pour les questions que personne ne posait, et deux
    # défauts vivants sont sortis en les écrivant — la porte affirmait quatre zéros
    # pour un locataire jamais mesuré, et deux fonctions Apple rendaient un nombre
    # sur une lecture échouée.
    #
    # Une plateforme neuve ajoute cinq cases d'un coup et fera rougir ce plafond.
    # C'est voulu : brancher une source sans la garder est ce qui a coûté le plus
    # cher ici, et c'est le seul mécanisme qui l'empêche sans relecture humaine.
    "guard-matrix.holes": 0,
}

# Les populations, pour qu'un compteur ne puisse pas baisser en SUPPRIMANT la
# surface. « Zéro indéterminée » sur zéro figure est vrai et ne dit rien.
_FLOOR: dict[str, int] = {
    "figures.total": 89,
    "tiles.total": 207,
    "pdf.total": 29,
    "gold-objects.total": 15,
    "ratchets.total": 18,
    "error-classes.total": 296,
    "ci.steps": 12,
    "ci.blocking": 12,
    "invariants.pairs": 12,
    "guard-matrix.cells": 40,
}


def test_the_document_still_describes_the_repository(gc) -> None:
    fresh = gc.build()
    current = _DOC.read_text(encoding="utf-8") if _DOC.exists() else ""
    assert current == fresh, (
        "`.claude/dev-docs/gold-coverage.md` ne décrit plus le dépôt.\n"
        "Remède : make gold-coverage\n\n"
        "Un document généré qui affirme un état périmé est pire qu'un document "
        "absent : il se lit comme une mesure."
    )


def test_no_counter_of_holes_ever_grows(counters) -> None:
    grown = [
        f"{key} : {counters[key]} contre un plafond de {ceiling}"
        for key, ceiling in sorted(_CEILING.items())
        if counters.get(key, 0) > ceiling
    ]
    assert not grown, (
        "Un trou de la carte s'est agrandi. Soit une surface neuve n'est pas "
        "attribuable à sa source, soit un agrégat est apparu là où aucun cliquet ne "
        "regarde.\n\n"
        "Regarde `.claude/dev-docs/gold-coverage.md` : les indéterminées sont triées "
        "EN TÊTE de leur tableau, avec leur motif.\n\n" + "\n".join(grown))


def test_the_ceiling_is_not_slack(counters) -> None:
    """Un plafond au-dessus de la mesure autorise en silence ce qu'il interdit."""
    missing = sorted(set(_CEILING) - set(counters))
    assert not missing, (
        f"compteur(s) que le document n'écrit plus : {missing}. Le plafond porte "
        "sur un nombre qui n'existe pas, donc il ne garde rien."
    )
    slack = {k: (c, counters[k]) for k, c in _CEILING.items() if c > counters[k]}
    assert not slack, (
        "Plafond(s) au-dessus de la mesure du jour — du mou. Descends-les à la "
        f"mesure : {slack}"
    )


def test_the_scan_is_not_vacuous(counters) -> None:
    """Un compteur de trous baisse aussi quand la population disparaît."""
    shrunk = [
        f"{key} : {counters.get(key, 0)}, il y en avait {floor} le 2026-09-12"
        for key, floor in sorted(_FLOOR.items())
        if counters.get(key, 0) < floor
    ]
    assert not shrunk, (
        "La population balayée a rétréci. « Zéro indéterminée » sur zéro figure est "
        "vrai et ne dit rien — c'est ainsi qu'un contrôle cesse de contrôler sans "
        "jamais rougir.\n\n"
        "Si la baisse est légitime (une vue supprimée), baisse le plancher DANS LE "
        "MÊME commit, avec la raison.\n\n" + "\n".join(shrunk))


def test_every_declared_raw_aggregate_still_exists(gc) -> None:
    """Une déclaration qui survit à ce qu'elle déclarait est du budget.

    Le jour où `freshness_monitor.py` cesse d'agréger `meta_campaigns`, sa ligne
    dans `_DECLARED_RAW_AGGREGATES` autorise gratuitement le prochain agrégat du
    même fichier sur la même table — que plus personne n'a décidé d'autoriser.
    C'est la classe `an-exemption-that-outlives-what-it-exempted`, et elle est la
    contrepartie exacte du passage du compteur à zéro.

    Mutation record — 2026-09-12 : une entrée ajoutée pour un fichier qui n'agrège
    pas cette table, ce test la nomme ; retirée, il passe.
    """
    gold, known = gc.scan_sql()
    files = gc.load_python()
    slicer = gc.Slicer(files, gc.build_call_index(files), gold, known,
                       gc.sql_wrappers(files))
    live = {(r.rel, t) for r in gc.all_reads(files, slicer) if r.aggregates
            for t in r.relations}
    stale = sorted(k for k in gc._DECLARED_RAW_AGGREGATES if k not in live)
    assert not stale, (
        "déclaration(s) d'agrégat brut qui ne désignent plus rien — le fichier "
        "n'agrège plus cette table, et la ligne est devenue du budget pour la "
        f"prochaine occurrence : {stale}"
    )


def test_the_two_declarations_of_the_ratchet_scope_agree(gc) -> None:
    """La colonne « dont hors cliquet » vaut ce que vaut cette égalité.

    `gold_coverage.py` recopie la portée de `test_the_metrics_layer_only_grows.py`
    pour pouvoir dire ce qu'elle NE couvre pas. Une règle recopiée diverge — c'est
    la classe la plus chère de ce dépôt — alors on compare les deux.
    """
    sys.path.insert(0, str(_ROOT / "tests"))
    import test_the_metrics_layer_only_grows as ratchet
    assert gc._RATCHET_SURFACES == ratchet._SURFACES, (
        "les répertoires balayés par le cliquet des agrégats ne sont plus ceux que "
        f"le générateur croit : {gc._RATCHET_SURFACES} vs {ratchet._SURFACES}")
    assert gc._RATCHET_DOORS == ratchet._DOORS, (
        f"les portes exemptées diffèrent : {gc._RATCHET_DOORS} vs {ratchet._DOORS}")
    facts = frozenset(t for tables in ratchet._FACTS.values() for t in tables)
    assert gc._RATCHET_FACTS == facts, (
        "la liste des tables de fait a bougé d'un côté seulement. Le document "
        "compterait « hors cliquet » des agrégats qui sont gardés, ou l'inverse.\n"
        f"  dans le générateur, en trop : {sorted(gc._RATCHET_FACTS - facts)}\n"
        f"  dans le cliquet, en trop   : {sorted(facts - gc._RATCHET_FACTS)}")
