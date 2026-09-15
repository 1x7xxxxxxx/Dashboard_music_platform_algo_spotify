"""Toute exécution de pytest doit apporter les greffons que `conftest.py` exige.

Type: Test
Uses: pytest, ast, yaml
Depends on: tests/conftest.py, .github/workflows/*.yml
Persists in: nothing

Ce qui a été mesuré (2026-09-15) — neuf jours de silence
--------------------------------------------------------
`tests/conftest.py` est chargé pour **toute** exécution de pytest, même celle qui ne
vise qu'un seul fichier. Il apporte donc ses propres exigences. Depuis le 2026-09-06
(20fd305) il déclare `pytest_configure_node`, un hook fourni par `pytest-xdist`.

Deux endroits lançaient pytest avec une liste de dépendances tenue **à la main**, sans
ce greffon :

* `.github/workflows/prod-health.yml` — `pip install pytest requests pandas`. Résultat :
  `PluginValidationError: unknown hook 'pytest_configure_node'`, « no tests ran in
  0.19s », `exit 3`. **Neuf exécutions consécutives en échec**, du 2026-09-07 au
  2026-09-15. Les seize sondes qui atteignent la production à travers Cloudflare n'ont
  rien exécuté pendant ce temps.
* `Makefile` — `PYTHON` figé sur le venv Windows, qui n'a pas `pytest-xdist` non plus.
  Même erreur, même `rc=3`, `make test` ne lançait aucun test.

Les deux ont été trouvés à un jour d'écart. Le premier a été corrigé **sans balayer les
frères** — et le frère était la sonde de production. C'est exactement ce que la règle
transverse 14 interdit.

Ce que ce garde vérifie
-----------------------
L'accord entre deux endroits qui n'ont aucune raison structurelle de rester d'accord :
les hooks que `conftest.py` DÉCLARE, et ce que chaque exécution de pytest INSTALLE.
Il lit le code (AST) et les workflows (YAML), jamais une liste écrite à la main.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
CONFTEST = REPO / "tests" / "conftest.py"
WORKFLOWS = REPO / ".github" / "workflows"

# Les hooks qu'un greffon apporte, et qui n'existent PAS dans pytest seul. Déclarer
# l'un d'eux sans son greffon fait sortir pytest en `rc=3` avant le moindre test.
_HOOK_OWNERS = {
    "pytest_configure_node": "pytest-xdist",
    "pytest_xdist_setupnodes": "pytest-xdist",
    "pytest_xdist_node_collection_finished": "pytest-xdist",
    "pytest_handlecrashitem": "pytest-xdist",
    "pytest_testnodedown": "pytest-xdist",
    "pytest_testnodeready": "pytest-xdist",
}

# Ces mécanismes installent l'environnement ENTIER depuis le manifeste : ils ne peuvent
# pas oublier un greffon, puisqu'ils ne choisissent rien.
_INSTALLS_EVERYTHING = ("uv sync", "uv run", "pip install -r", "pip install -e")


def _plugins_the_conftest_requires() -> set[str]:
    tree = ast.parse(CONFTEST.read_text(encoding="utf-8"))
    needed = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = _HOOK_OWNERS.get(node.name)
            if owner:
                needed.add(owner)
    return needed


def _pytest_steps() -> list[tuple[str, str, str]]:
    """(workflow, nom du step, tout le `run:` du job) pour chaque step qui lance pytest."""
    out = []
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        try:
            doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:                      # pragma: no cover
            pytest.fail(f"{wf.name} n'est pas un YAML lisible : {exc}")
        for job in (doc.get("jobs") or {}).values():
            steps = job.get("steps") or []
            job_runs = "\n".join(str(s.get("run", "")) for s in steps)
            for s in steps:
                run = str(s.get("run", ""))
                if "pytest" in run and "pip install" not in run:
                    out.append((wf.name, s.get("name") or "(sans nom)", job_runs))
    return out


def test_every_workflow_that_runs_pytest_installs_the_required_plugins():
    """Le défaut coûtait neuf jours de sonde muette. Il ne se voit pas à la lecture."""
    required = _plugins_the_conftest_requires()
    if not required:
        pytest.skip("`conftest.py` ne déclare aucun hook fourni par un greffon")

    missing = []
    for wf, step, job_runs in _pytest_steps():
        if any(tok in job_runs for tok in _INSTALLS_EVERYTHING):
            continue                                   # le manifeste fait foi
        for plugin in sorted(required):
            if plugin not in job_runs:
                missing.append(f"{wf} · « {step} » n'installe pas {plugin}")

    assert not missing, (
        "`tests/conftest.py` déclare un hook fourni par un greffon que ces exécutions "
        "n'installent pas. pytest sortira en `rc=3` — « no tests ran » — AVANT le "
        "moindre test, et le workflow paraîtra simplement rouge sans dire pourquoi :\n  "
        + "\n  ".join(missing)
        + "\n\nAjouter le greffon à la liste, ou passer par `uv sync` qui lit le "
        "manifeste et ne peut rien oublier."
    )


def test_the_extraction_sees_the_real_workflows_and_the_real_hooks():
    """Non-vacuité : deux lectures vides seraient d'accord et ne prouveraient rien.

    C'est le mode d'échec silencieux de ce garde. Si `_plugins_the_conftest_requires`
    cesse de reconnaître les hooks, ou si `_pytest_steps` ne trouve plus aucun step,
    le test ci-dessus passe sur du néant — exactement la forme du défaut qu'il garde.
    """
    required = _plugins_the_conftest_requires()
    assert "pytest-xdist" in required, (
        "`conftest.py` ne déclare plus aucun hook xdist d'après l'AST. Soit les hooks "
        "ont été retirés — et alors ce fichier peut disparaître — soit l'extraction "
        "est cassée et ne garde plus rien."
    )

    steps = _pytest_steps()
    assert steps, (
        "aucun step de workflow ne lance pytest d'après la lecture YAML : l'extraction "
        "est cassée, ou les workflows ont changé de forme."
    )
    assert any(wf == "prod-health.yml" for wf, _, _ in steps), (
        "`prod-health.yml` n'est plus vu comme lançant pytest — c'est précisément le "
        f"fichier qui a coûté neuf jours. Vus : {sorted({w for w, _, _ in steps})}"
    )
