"""Une durée se lit dans la colonne qui la porte, jamais dans l'écart de deux horodatages.

Type: Test
Uses: pytest, ast
Depends on: src/utils/dag_run_logger.py, airflow/dags/*_daily.py
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
`record_tenant_run` écrivait `started_at = ended_at = now`. Quatre des cinq DAGs de
collecte passent par elle — seul Meta tenait ses propres horodatages. Donc quatre
plateformes sur cinq portaient une durée de **zéro** dans `etl_run_log`, et toute
moyenne calculée dessus intégrait des zéros qui n'étaient pas des mesures.

Deux moitiés à garder, et elles se contrediraient si on n'en gardait qu'une :

1. **L'appelant mesure.** Un DAG qui enregistre un succès sans chronométrer réinstalle
   le zéro. Le garde lit l'AST : un mot-clé `duration_ms` sur chaque appel.
2. **La ligne survit à l'absence de mesure.** `started_at` est NOT NULL depuis la
   migration 006. Y écrire NULL pour dire « je ne sais pas » fait lever l'INSERT, que
   le `except` de la fonction avale : la ligne disparaît — l'infirmité même que ce
   journal a été écrit pour retirer. L'inconnu se dit dans `duration_ms`, qui est
   nullable, et c'est la colonne que lisent les surfaces.

D'où le troisième prédicat : personne ne doit reconstruire une durée par
`ended_at - started_at`, puisque cet écart vaut zéro quand la mesure manque.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DAGS = sorted((_ROOT / "airflow" / "dags").glob("*_daily.py"))


def _calls(tree: ast.AST, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == name]


def test_every_recorded_success_carries_a_measured_duration() -> None:
    """Un enregistrement sans chronomètre réinstalle le zéro, en silence."""
    naked = []
    for path in _DAGS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _calls(tree, "record_tenant_success"):
            if not any(kw.arg == "duration_ms" for kw in call.keywords):
                naked.append(f"{path.name}:{call.lineno}")
    assert not naked, (
        "ces appels enregistrent un succès sans mesurer sa durée, donc écrivent "
        f"un zéro que rien ne distingue d'une collecte instantanée : {naked}")


def test_a_run_without_a_measured_duration_still_leaves_a_row() -> None:
    """`started_at` est NOT NULL : y écrire NULL supprime la ligne, pas la durée."""
    src = (_ROOT / "src" / "utils" / "dag_run_logger.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    assign = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "_started" for t in n.targets))
    assert isinstance(assign.value, ast.IfExp), (
        "_started doit choisir entre une valeur mesurée et un repli, pas être constant")
    fallback = assign.value.orelse
    assert not (isinstance(fallback, ast.Constant) and fallback.value is None), (
        "le repli d'une durée inconnue écrit NULL dans une colonne NOT NULL : "
        "l'INSERT lève, le `except` l'avale, et la ligne disparaît — c'est le trou "
        "que ce journal existe pour retirer. L'inconnu se dit dans `duration_ms`.")


def test_no_surface_rebuilds_a_duration_from_two_timestamps() -> None:
    """L'écart vaut zéro quand la mesure manque : il ne peut pas servir de durée."""
    pattern = re.compile(r"ended_at\s*-\s*started_at")
    offenders = []
    for path in list((_ROOT / "src").rglob("*.py")) + list((_ROOT / "airflow").rglob("*.py")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and not line.lstrip().startswith("#"):
                offenders.append(f"{path.relative_to(_ROOT)}:{i}")
    assert not offenders, (
        "une durée reconstruite par soustraction rend zéro pour toute exécution non "
        f"chronométrée : lire `duration_ms`, qui vaut NULL dans ce cas — {offenders}")
