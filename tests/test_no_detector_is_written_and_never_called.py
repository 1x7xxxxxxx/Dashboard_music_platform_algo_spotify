"""A detector nothing calls is worse than a missing one: it looks like coverage.

Installed 2026-08-22. `src/utils/monitoring_checks.py` held `silent_zero_findings`,
written for "configured tenant × platform with zero recent rows — the silent-success
class". It had a docstring naming the class, two unit tests, and **no caller** in
`src/`, `airflow/` or `tools/`. Anyone reading the module concluded the class was
covered. It was — but by `readiness_red_flags`, somewhere else, and only by accident
of that function computing the same predicate.

Two failure modes, and this file rules out both:
  * the detector is genuinely missing from the pipeline → the class is unguarded
    while the code says otherwise;
  * the detector duplicates a live one → two voices for one finding, which is
    `watchdog-becomes-the-noise`.

`silent_zero_findings` was the second, so it was deleted rather than wired.

The scope is `monitoring_checks.py` on purpose: it is the module whose entire reason
for existing is to be called by the nightly DAG. A pure helper elsewhere may
legitimately have one caller or none.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "src" / "utils" / "monitoring_checks.py"
# Where a detector must be consumed to count as wired.
_CONSUMERS = [REPO / "airflow" / "dags", REPO / "src", REPO / "tools"]


def _public_functions() -> list[str]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    return [n.name for n in tree.body
            if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]


def _is_called_somewhere(name: str) -> bool:
    for root in _CONSUMERS:
        for path in root.rglob("*.py"):
            if path == MODULE:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    f = node.func
                    called = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                    if called == name:
                        return True
    return False


def test_every_monitoring_check_has_a_production_caller():
    names = _public_functions()
    assert names, "no public function found — the AST parse is reading the wrong file"

    orphans = sorted(n for n in names if not _is_called_somewhere(n))
    assert not orphans, (
        f"{orphans} are defined in monitoring_checks.py and called by nothing outside "
        "it. A tested detector that never runs reads as coverage in the error-class "
        "catalogue while guarding nothing.\n"
        "Wire it into alert_monitor, or delete it and say in the module why — the "
        "third option, leaving it, is the one that already cost us."
    )


def test_the_deleted_detector_stays_deleted():
    """Re-adding it without a caller would recreate the exact situation.

    Named explicitly rather than left to the generic check above, because the reason
    it went is not "it was unused" but "it duplicated a live check" — a future reader
    tempted to restore it needs that sentence, not just a red test.
    """
    src = MODULE.read_text(encoding="utf-8")
    assert "def silent_zero_findings" not in src, (
        "silent_zero_findings is back. Its predicate is already computed by "
        "artist_readiness.platform_status as NO_DATA and reported nightly by "
        "readiness_red_flags — two readers for one fact is watchdog-becomes-the-noise."
    )
    assert "silent_zero_findings" in src, (
        "the note explaining why it was removed went with it. Without the note the "
        "next person re-adds it, which is how a decision becomes a cycle."
    )
