"""La CI doit cloner l'HISTOIRE que ses propres gardes lisent.

Type: Test
Uses: yaml
Depends on: .github/workflows/ci.yml, tools/dev/error_class_health.py
Persists in: nothing

Le défaut
---------
`actions/checkout` clone à PROFONDEUR 1 par défaut. `tools/dev/error_class_health.py`
dérive son instantané de `git log` — la récidive par classe, la date de naissance de
chaque entrée. Dans un clone superficiel il ne voit qu'un commit, produit un autre JSON,
et `test_the_snapshot_still_describes_the_catalogue` échoue par construction.

Mesuré le 2026-09-17 : **1 027 commits en local, 1 dans un clone `--depth 1`**, JSON
différent, confirmé en rejouant le constructeur dans un clone superficiel réel.

Pourquoi il a tenu sept runs
----------------------------
Il est INVISIBLE en local : l'histoire y est, donc le test passe. Seule la CI le voyait,
et un rouge de CI ne remonte à personne tant qu'on ne le regarde pas. Famille
`un-garde-qui-ne-garde-pas` — le garde existait, son environnement l'empêchait de passer.

⚠️ Ce test ne vérifie pas que TOUT outil lisant git tourne en CI : il vérifie que les
checkout de `ci.yml` ramènent l'histoire. Un outil lisant git dans un AUTRE workflow
reste non couvert.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_WORKFLOWS = sorted(
    (Path(__file__).resolve().parents[1] / ".github/workflows").glob("*.yml"))
_BUILDER = Path(__file__).resolve().parents[1] / "tools/dev/error_class_health.py"


def _checkout_steps() -> list[tuple[str, str, dict]]:
    """(workflow, job, étape) pour chaque checkout de CHAQUE workflow.

    ⚠️ Élargi le 2026-09-17 : la première version ne lisait que `ci.yml`. Le balayage
    des frères a trouvé **quatre autres checkout superficiels** dans
    `security-nightly.yml`, dont celui du job qui lance la suite complète — et ce
    job porte `continue-on-error: true`, donc son vert ne disait RIEN. Un garde qui
    ne regarde qu'un fichier laisse la classe vivante dans les trois autres.
    """
    steps = []
    for wf in _WORKFLOWS:
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        for jname, job in (doc.get("jobs") or {}).items():
            for step in job.get("steps", []):
                if str(step.get("uses", "")).startswith("actions/checkout"):
                    steps.append((wf.name, jname, step))
    return steps


def test_the_builder_still_reads_git() -> None:
    """Si le constructeur cessait de lire git, cette exigence deviendrait vide.

    ⚠️ Première version : `'"git"' in src`. Elle a été refusée par
    `test_a_guard_reads_structure_not_text` — et à raison : la chaîne `"git"`
    apparaît des dizaines de fois dans les commentaires de ce fichier, qui RACONTE
    ce qu'il fait de git. Le test serait resté vert sur un constructeur qui ne
    l'appelle plus. On interroge donc la STRUCTURE : un appel `subprocess.run`
    dont le premier argument porte le littéral `git`.
    """
    import ast

    tree = ast.parse(_BUILDER.read_text(encoding="utf-8"))
    runs_git = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "attr", None) not in {"run", "check_output", "Popen"}:
            continue
        for arg in node.args[:1]:
            consts = [arg] if isinstance(arg, ast.Constant) else list(
                getattr(arg, "elts", []))
            if any(isinstance(c, ast.Constant) and c.value == "git" for c in consts):
                runs_git = True
    assert runs_git, (
        "error_class_health.py n'appelle plus `git` par subprocess : ce test ne "
        "démontre plus rien, le retirer ou le réécrire plutôt que de le laisser "
        "vert par vacuité")


# Ce qui LIT l'histoire : la suite ENTIÈRE (elle contient le garde du catalogue) et
# l'outillage de santé. Un job qui lance UN fichier de test — `pytest
# tests/test_prod_health.py` — n'a pas besoin de l'histoire, et la lui imposer
# coûterait du temps de clone pour rien.
_READS_GIT = re.compile(r"pytest\s+tests/(\s|$)|error_class_health|error-health")


def _needs_history(job: dict) -> bool:
    return any(_READS_GIT.search(str(step.get("run", "")))
               for step in job.get("steps", []))


def _shallow_jobs(doc: dict) -> list[str]:
    """Jobs that READ git history but check out at depth 1."""
    out = []
    for jname, job in (doc.get("jobs") or {}).items():
        if not _needs_history(job):
            continue
        for step in job.get("steps", []):
            if not str(step.get("uses", "")).startswith("actions/checkout"):
                continue
            if str((step.get("with") or {}).get("fetch-depth", "")) != "0":
                out.append(jname)
    return out


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity on a FABRICATED workflow: a job running the health tool (it reads
    `git log`) behind a default shallow checkout; the corrected depth; and a job that
    reads no history, which must not be asked to fetch it."""
    runs_health = "python3 tools/dev/error_class_health.py --check"
    defect = {"jobs": {"gates": {"steps": [{"uses": "actions/checkout@v6"},
                                           {"run": runs_health}]}}}
    assert _shallow_jobs(defect) == ["gates"], "a history reader at depth 1 must be seen"
    fixed = {"jobs": {"gates": {"steps": [{"uses": "actions/checkout@v6",
                                           "with": {"fetch-depth": 0}},
                                          {"run": runs_health}]}}}
    assert _shallow_jobs(fixed) == []
    no_history = {"jobs": {"deploy": {"steps": [{"uses": "actions/checkout@v6"},
                                                {"run": "railway up --detach"}]}}}
    assert _shallow_jobs(no_history) == [], "a job that reads no history is exempt"


def test_only_the_jobs_that_read_history_are_required_to_fetch_it() -> None:
    """Le garde vise un GESTE (lire `git log`), pas tous les checkout du dépôt.

    ⚠️ La première version exigeait `fetch-depth: 0` PARTOUT. Elle dénonçait
    `cd-release::deploy-railway`, qui ne lance aucun pytest, et
    `prod-health::prod-health`, qui n'en lance qu'UN fichier — deux faux positifs
    qui auraient appris à ignorer ce garde.
    """
    shallow = [f"{wf.name}::{j}" for wf in _WORKFLOWS
               for j in _shallow_jobs(yaml.safe_load(wf.read_text(encoding="utf-8")))]
    assert not shallow, (
        "ces jobs LISENT l'histoire git et clonent en profondeur 1 : "
        + ", ".join(sorted(set(shallow))) + ".\n"
        "`tools/dev/error_class_health.py` dérive son instantané de `git log` : sans "
        "l'histoire il produit un autre JSON, et le garde du catalogue échoue par "
        "CONSTRUCTION — vert en local, rouge en CI, sept runs d'affilée le 2026-09-17.\n"
        "Remède : `with: { fetch-depth: 0 }` sur le checkout de ces jobs.")


def test_at_least_one_job_actually_reads_the_history() -> None:
    """Sans ce contrôle, supprimer la suite de la CI rendrait le test vert par vacuité."""
    reading = [f"{wf.name}::{j}" for wf in _WORKFLOWS
               for j, job in (yaml.safe_load(wf.read_text(encoding="utf-8")).get("jobs")
                              or {}).items()
               if _needs_history(job)]
    assert reading, (
        "aucun job de `.github/workflows/` ne lance la suite entière ni l'outillage "
        "de santé : ce garde ne démontre plus rien")
