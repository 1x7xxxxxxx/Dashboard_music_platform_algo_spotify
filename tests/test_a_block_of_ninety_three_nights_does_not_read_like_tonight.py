"""Une alerte qui ne change jamais cesse d'être lue.

Type: Test
Uses: pytest
Depends on: src/utils/collection_outcomes.py, airflow/dags/alert_monitor.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10, en production)
----------------------------------------------
Le locataire 12 échoue sur Meta **toutes les nuits depuis le 2026-06-19** — 93 nuits
consécutives, toujours la même cause :

    (#200) Ad account owner has NOT grant ads_management or ads_read permission

Aucune exécution ne peut la retirer : elle nomme un geste humain à faire chez Meta.
Or l'alerte l'écrivait à l'identique la nuit 1 et la nuit 93, et le locataire 12
tenait la ligne d'objet tous les soirs depuis trois mois. Un objet qui ne change
jamais n'est plus lu — et le soir où une vraie panne s'y ajoute, personne ne la voit.

Ce qui est gardé ici, et ce qui ne l'est pas
--------------------------------------------
On ne fait rien taire : un blocage installé garde sa ligne complète dans le corps,
avec son ancienneté et sa cause. Ce qui change, c'est qu'on puisse le **distinguer**
de ce qui vient de casser — dans l'ordre de la liste, dans la couleur, et dans le
sujet.

La décision vit dans `src/utils/`, pas dans le DAG, pour une raison déjà payée ici :
un module de DAG ne s'importe pas hors de son conteneur, donc un seuil écrit dedans
est un seuil qu'aucun test n'exerce jamais.
"""
from __future__ import annotations

import ast
from pathlib import Path

from src.utils.collection_outcomes import (
    describe_failure_age, failure_age_nights, is_long_standing, split_by_age)

_DAG = (Path(__file__).resolve().parents[1]
        / "airflow" / "dags" / "alert_monitor.py").read_text(encoding="utf-8")

_TONIGHT = {'artist_name': 'GRiNCH', 'platform': 'soundcloud', 'failing_nights': 1,
            'last_success': '2026-09-09 03:12:00'}
_BENKEN = {'artist_name': 'Benken', 'platform': 'meta', 'failing_nights': 93,
           'last_success': None}


def test_the_real_production_case_does_not_read_like_a_fresh_break() -> None:
    """93 nuits et une nuit ne peuvent pas produire la même phrase."""
    assert describe_failure_age(_TONIGHT) == "cette nuit"
    said = describe_failure_age(_BENKEN)
    assert "93" in said and "jamais" in said, said
    assert said != describe_failure_age(_TONIGHT)


def test_a_long_standing_block_never_takes_the_subject_line() -> None:
    fresh, stuck = split_by_age([_BENKEN, _TONIGHT])
    assert [p['artist_name'] for p in fresh] == ['GRiNCH']
    assert [p['artist_name'] for p in stuck] == ['Benken']


def test_a_night_with_only_old_blocks_still_reports_them() -> None:
    """Distinguer n'est pas taire : le corps garde la ligne, le sujet garde le compte."""
    fresh, stuck = split_by_age([_BENKEN])
    assert fresh == [] and len(stuck) == 1
    assert "93 nuits" in describe_failure_age(stuck[0])


def test_what_broke_tonight_is_listed_first() -> None:
    """L'ordre porte l'actionnabilité : ce qu'une exécution peut corriger d'abord."""
    problems = [_BENKEN, _TONIGHT]
    problems.sort(key=failure_age_nights)
    assert problems[0] is _TONIGHT


def test_an_unreadable_age_alerts_rather_than_being_filed_away() -> None:
    """Un incident dont l'ancienneté est illisible ne se range pas en silence."""
    for bad in ({}, {'failing_nights': None}, {'failing_nights': 'douze'},
                {'failing_nights': 0}, {'failing_nights': -4}):
        assert not is_long_standing(bad), bad
        assert describe_failure_age(bad) == "cette nuit", bad


def test_the_alert_reads_the_age_instead_of_recomputing_it() -> None:
    """Le DAG doit passer par le module, sinon le garde ci-dessus ne garde rien."""
    tree = ast.parse(_DAG)
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                and (n.module or '').endswith('collection_outcomes') for a in n.names}
    assert {'describe_failure_age', 'split_by_age'} <= imported, (
        "alert_monitor n'importe plus les décisions d'ancienneté : si elles sont "
        "réécrites en ligne dans le DAG, aucun test ne peut les atteindre — c'est "
        f"exactement ce que ce fichier existe pour empêcher. Importé : {imported}")
    inline = [n for n in ast.walk(tree)
              if isinstance(n, ast.Compare)
              and isinstance(n.left, ast.Call)
              and isinstance(n.left.func, ast.Attribute)
              and n.left.func.attr == 'get'
              and any(isinstance(a, ast.Constant) and a.value == 'failing_nights'
                      for a in n.left.args)]
    assert not inline, (
        "le seuil d'ancienneté est recalculé en ligne dans le DAG, hors de portée "
        "de tout test : passer par is_long_standing/split_by_age")
