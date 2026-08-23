"""
Guard — no verdict on the SHAPE of data until the data is proven fresh (R42).

Type: Sub
Uses: datetime, ast
Triggers: pytest
Depends on: src/utils/quality_gate.py, airflow/dags/data_quality_check.py
Persists in: nothing

Error class: shape-judged-on-dead-data.

Moses/Gavish/Vorwerck (*Data Quality Fundamentals*, p.144) keep Freshness and
Distribution as separate pillars, and p.86 makes the circuit breaker the thing that
orders them. streaMLytics had already paid for the inverse: `data_quality_check` has
never run once, and its Meta task would have reported GREEN on the most stale source in
production because it measured `MAX(collected_at)` — the WRITE time, which advances every
night as the DAG rewrites the same old rows — instead of `MAX(day_date)`, which stopped
in 2024.

Two things are pinned here:

* the predicate reads the day the DATA carries, and a stale or absent source opens the
  circuit;
* `data_quality_check` actually calls it. The DAG cannot be imported in any test of this
  repo (the installed Airflow rejects `schedule_interval`), so a runtime assertion would
  skip in silence — the structural one is the only one that can hold.
"""

import ast
from datetime import date, timedelta
from pathlib import Path

from src.utils.quality_gate import (
    MAX_SOURCE_AGE_DAYS,
    abstention_note,
    source_is_fresh_enough,
)

_ROOT = Path(__file__).resolve().parents[1]
_DAG = _ROOT / "airflow" / "dags" / "data_quality_check.py"
_TODAY = date(2026, 8, 23)


def test_fresh_data_lets_the_checks_run():
    assert source_is_fresh_enough(_TODAY - timedelta(days=1), _TODAY)


def test_stale_data_opens_the_circuit():
    assert not source_is_fresh_enough(_TODAY - timedelta(days=30), _TODAY)


def test_the_meta_shaped_failure_opens_the_circuit():
    """La forme exacte du défaut mesuré : donnée de 2024, écriture d'il y a 8 h."""
    assert not source_is_fresh_enough(date(2024, 9, 30), _TODAY)
    note = abstention_note(date(2024, 9, 30), _TODAY)
    assert "périmée" in note and "2024-09-30" in note, (
        "l'abstention doit NOMMER la date portée par la donnée — c'est la seule chose "
        "qui distingue « périmé » de « en panne »"
    )


def test_an_absent_source_is_not_a_shape_verdict():
    assert not source_is_fresh_enough(None, _TODAY)
    assert "aucune donnée" in abstention_note(None, _TODAY)


def test_the_threshold_stays_a_daily_cadence():
    assert 1 <= MAX_SOURCE_AGE_DAYS <= 7, (
        "la timeline S4A est quotidienne ; au-delà d'une semaine ce n'est plus du "
        "retard, et la source muette appartient à freshness_monitor"
    )


def test_the_dag_opens_the_circuit_before_judging_anything():
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    called = {
        n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
        for n in ast.walk(tree) if isinstance(n, ast.Call)
    }
    assert "source_is_fresh_enough" in called, (
        "check_spotify_data_consistency doit passer par le circuit breaker avant de "
        "juger la forme des données"
    )


def test_the_superseded_meta_task_is_gone():
    """Une seconde voix sur la fraîcheur, et c'est la fausse qui parlait le plus fort."""
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "check_meta_ads_freshness" not in defined, (
        "check_meta_ads_freshness mesurait la fraîcheur sur la date d'écriture et "
        "serait passée au vert sur la source la plus morte de la prod ; "
        "freshness_monitor fait le même travail correctement"
    )


def test_a_business_finding_never_fails_the_task():
    """Un détecteur qui part en FAILED sur un constat devient sa propre panne.

    `check_dag_failures` en ferait une alerte quotidienne non actionnable — exactement
    le bruit que la politique d'alerte du dépôt cherche à supprimer.
    """
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "check_spotify_data_consistency")
    raised = [
        n.lineno for n in ast.walk(fn)
        if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
        and getattr(n.exc.func, "id", "") == "ValueError"
    ]
    assert not raised, (
        f"ligne(s) {raised} : le constat métier doit remonter par XCom, pas par une "
        f"exception qui met la tâche en FAILED"
    )
