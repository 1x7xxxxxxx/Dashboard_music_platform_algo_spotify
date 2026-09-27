"""R230 — every data-quality check is filed under a category, and every pointer is real.

The owner asked for checks by family (duplicates, impossible values, time breaks,
abnormal variations, cross-platform divergences, mapping, missing data). The catalogue
`tools/dev/dq_catalogue.py` files the checks that already run. Two ways it could lie:
a pointer to a function that no longer exists, and a nightly check added without a
category — it would run and never appear where the owner looks.
"""
import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("dq_catalogue", ROOT / "tools/dev/dq_catalogue.py")
dq = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = dq
_SPEC.loader.exec_module(dq)

# alert_monitor checks that watch the OPERATIONS, not the data — named, with why.
NOT_DATA = {
    "check_credentials_all": "jetons des plateformes",
    "check_dag_failures": "tâches Airflow en échec",
    "check_billing_sync": "facturation Stripe",
    "check_central_apps": "applications centrales",
    "check_canary_health": "le canari de production",
    "check_canary_preflight": "le canari de production",
    "check_onboarding_readiness": "la mise en route d'un artiste",
    "check_offsite_backup": "la sauvegarde hors site",
    "check_app_errors": "les erreurs applicatives",
    "check_ops_alerts": "les alertes Prometheus",
}


def functions_in(path: Path) -> set[str]:
    return {n.name for n in ast.walk(ast.parse(path.read_text()))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_every_pointer_resolves_to_a_function():
    dead = [c.pointer for c in dq.CHECKS
            if c.pointer.split("::")[1] not in functions_in(ROOT / c.pointer.split("::")[0])]
    assert not dead, f"catalogue pointers to nothing: {dead}"


def test_every_check_has_a_known_category_and_pillar():
    bad = [c.pointer for c in dq.CHECKS
           if c.category not in dq.CATEGORIES or c.pillar not in dq.PILLARS]
    assert not bad, bad


def test_every_category_has_a_check_or_says_what_is_missing():
    empty = [cat for cat in dq.CATEGORIES
             if not any(c.category == cat for c in dq.CHECKS) and cat not in dq.GAPS]
    assert not empty, f"categories with no check and no declared gap: {empty}"


def test_every_nightly_check_is_filed():
    nightly = {f for f in functions_in(ROOT / "airflow/dags/alert_monitor.py")
               if f.startswith("check_")}
    filed = {c.pointer.split("::")[1] for c in dq.CHECKS
             if c.pointer.startswith("airflow/dags/alert_monitor.py")}
    unfiled = sorted(nightly - filed - set(NOT_DATA))
    assert not unfiled, (
        f"nightly checks in no category: {unfiled} — file them in tools/dev/dq_catalogue.py "
        "or, if they watch operations and not data, in NOT_DATA with why")
    stale = sorted(set(NOT_DATA) - nightly)
    assert not stale, f"NOT_DATA names checks that no longer exist: {stale}"
