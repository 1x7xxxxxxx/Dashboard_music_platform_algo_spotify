"""Guard: a blocking gate may fail the build; it may not make the rest invisible.

Type: Test
Uses: pytest, yaml
Depends on: .github/workflows/ci.yml
Persists in: nothing

Ce qui a été mesuré (2026-09-06)
--------------------------------
Les gardes de classes d'erreur étaient l'étape **10 sur 15** d'un job unique. Un
échec là sautait les cinq suivantes, dont `Run tests`. La suite n'a donc PAS tourné
pendant **27 exécutions consécutives** (2026-09-04 → 2026-09-06), sur une cause qui
n'avait aucun rapport avec elle : deux gardes lisaient le `.env` du poste. Vingt-sept
commits sont partis sur main avec un seul signal rouge, toujours le même, et rien
derrière. Le coût n'a pas été le temps — il a été l'ignorance.

Ce que ce garde demande, et pourquoi il a changé de forme (2026-09-16)
---------------------------------------------------------------------
Il lisait `jobs["lint-and-test"]["steps"]`, un nom de job en dur. R109 a découpé la
CI en deux jobs indépendants (`gates` et `suite` en quatre shards) — une forme qui
satisfait la propriété **structurellement** : deux jobs sans `needs:` ne peuvent pas
se cacher l'un l'autre. Le garde aurait explosé sur un fichier meilleur que celui
qu'il gardait.

Il pose donc la question au bon niveau, en deux temps :

1. **entre jobs** — aucun job qui lance la suite ne peut dépendre (`needs:`, même
   transitivement) d'un job qui porte une porte. C'est la panne de septembre
   re-créée à l'échelle du job, et elle serait encore plus silencieuse : un job
   « skipped » ne produit même pas de log ;
2. **dans un job** — toute étape postérieure à l'installation doit survivre à un
   échec antérieur, sauf si elle se DÉCLARE porte par le suffixe `(blocking)`.

Aucun nom de job n'est écrit ici. Renommer, ajouter ou scinder un job reste libre ;
ce qui ne l'est pas, c'est de remettre la suite derrière une porte.
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
# identical noise instead of a report.
_SETUP_STEPS = (
    "Install uv",
    "Set up Python 3.11",
    "Install system dependencies (build tools for any wheel-less package)",
    "Install dependencies from lockfile",
)

_SURVIVES = ("!cancelled()", "always()", "success() || failure()")

# Le marqueur qui dit « cette étape a le droit d'arrêter la construction ».
#
# Ces étapes étaient listées par leur nom littéral jusqu'au 2026-09-15 — et renommer
# l'une d'elles (`deterministic` → `static`) a fait rougir ce garde sur un fichier
# PARFAITEMENT juste. Le garde avait raison de parler, mais il parlait de la mauvaise
# chose : il lisait un NOM là où la question est un RÔLE.
_GATE_SUFFIX = "(blocking)"


def _jobs() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]


def _is_a_declared_gate(step: dict) -> bool:
    return str(step.get("name", "")).strip().endswith(_GATE_SUFFIX)


def _runs_the_suite(job: dict) -> bool:
    return any("pytest tests/" in str(s.get("run", "")) for s in job.get("steps", []))


def _carries_a_gate(job: dict) -> bool:
    return any(_is_a_declared_gate(s) for s in job.get("steps", []))


def _needs(job: dict) -> list[str]:
    n = job.get("needs")
    if n is None:
        return []
    return [n] if isinstance(n, str) else list(n)


def _needs_closure(name: str, jobs: dict) -> set[str]:
    """Tous les jobs dont `name` dépend, directement ou non."""
    seen: set[str] = set()
    stack = list(_needs(jobs.get(name, {})))
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in jobs:
            continue
        seen.add(cur)
        stack.extend(_needs(jobs[cur]))
    return seen


def test_no_job_that_runs_the_suite_waits_on_a_gate():
    """La panne de septembre, posée à l'échelle du job."""
    jobs = _jobs()
    suite = [n for n, j in jobs.items() if _runs_the_suite(j)]
    assert suite, (
        "aucun job de ci.yml ne lance `pytest tests/` — si la CI a cessé de lancer la "
        "suite, c'est ÇA le constat, pas la comptabilité de ce test."
    )
    gates = {n for n, j in jobs.items() if _carries_a_gate(j)}
    assert gates, (
        f"aucun job ne porte d'étape suffixée '{_GATE_SUFFIX}' : soit les portes ont "
        "disparu, soit le marqueur est cassé. Dans les deux cas ce fichier ne garde plus rien."
    )

    chained = {n: sorted(_needs_closure(n, jobs) & gates) for n in suite}
    bad = {n: g for n, g in chained.items() if g}
    assert not bad, (
        f"ces jobs de suite attendent une porte : {bad}.\n"
        "Une porte rouge les rendrait « skipped » — pas même un log. C'est la panne des "
        "27 exécutions de 2026-09-04→06, re-créée à l'échelle du job et plus silencieuse "
        "encore. Les deux doivent partir en parallèle ; le job de porte échoue tout seul."
    )


def test_every_step_after_setup_reports_rather_than_disappears():
    """One skipped step is a gap in the report, not just a saved minute."""
    hidden: list[str] = []
    for name, job in _jobs().items():
        steps = job.get("steps", [])
        names = [s.get("name") for s in steps]
        present = [names.index(n) for n in _SETUP_STEPS if n in names]
        if not present:
            continue
        for s in steps[max(present) + 1:]:
            if not any(tok in str(s.get("if", "")) for tok in _SURVIVES) \
                    and not _is_a_declared_gate(s):
                hidden.append(f"{name} → {s.get('name')}")

    assert not hidden, (
        f"{hidden} vanish from the report as soon as anything before them fails. "
        f"A step whose name ends with '{_GATE_SUFFIX}' is exempt — it is what may "
        "legitimately stop the build — but nothing after them should go unreported."
    )


def test_the_gate_marker_names_the_gates_and_nothing_else():
    """Non-vacuité : un suffixe qui n'attrape rien exempterait tout, ou rien.

    Sans cette assertion, remplacer `_GATE_SUFFIX` par une chaîne absente rendrait
    le test ci-dessus rouge sur les portes, et le remplacer par `""` le rendrait
    vert sur n'importe quel fichier. Les deux directions sont épinglées.
    """
    jobs = _jobs()
    steps = [s for j in jobs.values() for s in j.get("steps", [])]
    gates = [s.get("name") for s in steps if _is_a_declared_gate(s)]

    assert len(gates) >= 3, (
        f"le marqueur '{_GATE_SUFFIX}' ne trouve plus que {len(gates)} porte(s) : "
        f"{gates}. Soit les portes ont été renommées sans lui, soit le marqueur est "
        "cassé — dans les deux cas le test d'à côté ne garde plus rien."
    )
    assert len(gates) < len(steps), (
        "le marqueur exempte TOUTES les étapes : il ne distingue plus rien."
    )
    assert not _is_a_declared_gate({"name": "Run tests"}), (
        "une étape ordinaire est prise pour une porte"
    )


def test_the_closure_actually_follows_a_chain():
    """Non-vacuité du calcul de dépendances : sans elle, `needs:` pourrait être ignoré.

    Un `_needs_closure` qui rendrait toujours l'ensemble vide rendrait le premier
    test vert quoi qu'on écrive dans le fichier — la forme d'aveuglement la plus
    courante de ce dépôt.
    """
    faux = {"a": {}, "b": {"needs": "a"}, "c": {"needs": ["b"]}}
    assert _needs_closure("c", faux) == {"a", "b"}
    assert _needs_closure("a", faux) == set()
