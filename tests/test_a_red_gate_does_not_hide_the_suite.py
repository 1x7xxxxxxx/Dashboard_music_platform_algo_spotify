"""Guard: a blocking gate may fail the build; it may not make the rest invisible.

Type: Utility
Uses: yaml, pathlib
Triggers: pytest
Persists in: nothing

Error class `red-gate-hides-every-step-behind-it`.

Measured 2026-09-06 with `gh run list`. `.github/workflows/ci.yml` runs the
error-class guards at step 10 of 15. A step failure skips every later step by
default, so `Run tests` — the suite, 3700+ tests, the only thing in this workflow
that can say the product still works — did not execute for **27 consecutive runs**
between 2026-09-04T22:36 and 2026-09-06T07:19. Twenty-seven commits reached `main`
on a single red signal that was always the same two guards, and nothing behind it.

The cause of those two guards' red had nothing to do with the suite: they read
`META_BUSINESS_ID` from the operator's `.env` (see
`guard-predicate-depends-on-the-host-env`). That is the shape of the class — the
gate that fails is rarely the thing you most need to see.

What this asserts is narrow on purpose: every step AFTER the first blocking gate
must declare a condition that survives an earlier failure. It does not ask the gate
to stop blocking — a red guard still fails the job. It asks that the job keep
reporting.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


CI = _repo_root() / ".github" / "workflows" / "ci.yml"

# The gates that are allowed to hide what follows them. Installing dependencies is
# one: nothing after it can run at all, so letting later steps try buys a wall of
# identical noise instead of a report. Everything after the LAST of these must
# survive an earlier failure.
_SETUP_STEPS = (
    "Install uv",
    "Set up Python 3.11",
    "Install system dependencies (build tools for any wheel-less package)",
    "Install dependencies from lockfile",
)

_SURVIVES = ("!cancelled()", "always()", "success() || failure()")


def _steps() -> list[dict]:
    doc = yaml.safe_load(CI.read_text(encoding="utf-8"))
    return doc["jobs"]["lint-and-test"]["steps"]


def test_the_suite_step_still_runs_when_an_earlier_gate_fails():
    """The 27-run outage, asked as one question."""
    steps = _steps()
    run_tests = [s for s in steps if s.get("name") == "Run tests"]
    assert run_tests, "ci.yml no longer has a step named 'Run tests'"
    cond = str(run_tests[0].get("if", ""))
    assert any(tok in cond for tok in _SURVIVES), (
        "`Run tests` is skipped whenever any earlier step fails. That is how the "
        "suite stopped running for 27 consecutive CI runs on 2026-09-04..06 while "
        "every one of them reported a failure — of something else. Give it "
        "`if: ${{ !cancelled() }}`; the job still fails on the gate."
    )


# Le marqueur qui dit « cette étape a le droit d'arrêter la construction ».
#
# Ces trois étapes étaient listées ICI, par leur nom littéral, jusqu'au 2026-09-15 —
# et renommer l'une d'elles (`deterministic` → `static`, quand son audit a cessé de
# rejouer 60 % de la suite) a fait rougir ce garde sur un fichier PARFAITEMENT juste.
# Le garde avait raison de parler, mais il parlait de la mauvaise chose : il lisait un
# NOM là où la question est un RÔLE.
#
# Le suffixe est la déclaration du rôle, vérifiée sur le fichier réel : il porte
# exactement les trois portes et rien d'autre. Une porte neuve s'exempte donc en se
# nommant, et un renommage ne casse plus rien.
_GATE_SUFFIX = "(blocking)"


def _is_a_declared_gate(step: dict) -> bool:
    return str(step.get("name", "")).strip().endswith(_GATE_SUFFIX)


def test_every_step_after_setup_reports_rather_than_disappears():
    """One skipped step is a gap in the report, not just a saved minute."""
    steps = _steps()
    names = [s.get("name") for s in steps]
    last_setup = max(names.index(n) for n in _SETUP_STEPS if n in names)
    hidden = [
        s.get("name") for s in steps[last_setup + 1:]
        if not any(tok in str(s.get("if", "")) for tok in _SURVIVES)
        and not _is_a_declared_gate(s)
    ]
    assert not hidden, (
        f"{hidden} vanish from the report as soon as anything before them fails. "
        f"A step whose name ends with '{_GATE_SUFFIX}' is exempt — it is what may "
        "legitimately stop the build — but nothing after them should go unreported."
    )


def test_the_gate_marker_names_the_gates_and_nothing_else():
    """Non-vacuité : un suffixe qui n'attrape rien exempterait tout, ou rien.

    Sans cette assertion, remplacer `_GATE_SUFFIX` par une chaîne absente rendrait
    le test ci-dessus rouge sur les trois portes, et le remplacer par `""` le rendrait
    vert sur n'importe quel fichier. Les deux directions sont épinglées.
    """
    steps = _steps()
    gates = [s.get("name") for s in steps if _is_a_declared_gate(s)]

    assert len(gates) >= 3, (
        f"le marqueur '{_GATE_SUFFIX}' ne trouve plus que {len(gates)} porte(s) : "
        f"{gates}. Soit les portes ont été renommées sans lui, soit le marqueur est "
        "cassé — dans les deux cas le test d'à côté ne garde plus rien."
    )
    assert len(gates) < len(steps), (
        "le marqueur exempte TOUTES les étapes : il ne distingue plus rien."
    )
    assert all(_is_a_declared_gate({"name": f"X {_GATE_SUFFIX}"}) for _ in (0,))
    assert not _is_a_declared_gate({"name": "Run tests"}), (
        "une étape ordinaire est prise pour une porte"
    )
