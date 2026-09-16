"""Une porte de CI ne modifie pas l'arbre qu'elle évalue.

Type: Test
Uses: pytest, yaml
Depends on: .github/workflows/*.yml
Persists in: nothing

Ce qui a été mesuré (2026-09-16)
---------------------------------
`uv run` **re-verrouille et re-synchronise** avant d'exécuter. L'étape
`Manifest consistency (blocking)`, qui vérifie l'accord entre `pyproject.toml`,
`requirements.txt` et `uv.lock`, lisait donc un `uv.lock` que sa propre commande venait
de réparer. Elle répondait « aucune dérive » sur un arbre qui en portait trois.

Le cas vivant : la PR #161 (Dependabot) bumpait `pyproject.toml` et `requirements.txt`
sans toucher `uv.lock` — Dependabot ne connaît pas ce format. Au commit testé,
`uv.lock` disait streamlit **1.62.0** et `pyproject.toml` **1.63.0**. **La porte est
passée verte et la PR a été mergée.**

Rejoué à la main sur le même arbre :

    .venv/bin/python tools/dev/check_manifest_consistency.py   → rc=1, 3 MANIFEST-DRIFT
    uv run           tools/dev/check_manifest_consistency.py   → rc=0, et uv.lock MODIFIÉ

Ce fichier a déjà retiré une étape pour exactement cette forme
-------------------------------------------------------------
`ci.yml` documente le retrait d'`Error-class schema completeness` le 2026-09-15 :
`audit_runner.py --fields` appelait `_write_ratchet()`, donc l'étape ÉCRIVAIT dans le
fichier qu'elle jugeait. La phrase écrite alors s'applique mot pour mot ici : « une
barrière qui modifie le fichier qu'elle juge ne peut pas être rejouée avec le même
sens, et son verdict dépend de l'ordre dans lequel on la lance ».

La leçon n'avait pas été généralisée : elle visait une commande, pas la FORME.
Ce garde pose la question sur toutes les étapes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOWS = _ROOT / ".github" / "workflows"

# `uv run` sans `--frozen` re-verrouille : toute étape qui l'emploie modifie
# potentiellement `uv.lock` avant de juger quoi que ce soit.
_MUTATES_UNLESS_FROZEN = "uv run"
_FREEZE = "--frozen"


def _steps_running_uv() -> list[tuple[str, str, str]]:
    """(workflow, job, étape) pour chaque `run:` qui invoque `uv run`."""
    out = []
    for path in sorted(_WORKFLOWS.glob("*.y*ml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, job in (doc.get("jobs") or {}).items():
            for step in (job.get("steps") or []):
                script = str(step.get("run", ""))
                if _MUTATES_UNLESS_FROZEN in script:
                    out.append((path.name, str(job_name), str(step.get("name", "?"))))
    return out


def _unfrozen_uv_lines() -> list[str]:
    bad = []
    for path in sorted(_WORKFLOWS.glob("*.y*ml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, job in (doc.get("jobs") or {}).items():
            for step in (job.get("steps") or []):
                for line in str(step.get("run", "")).splitlines():
                    bare = line.strip()
                    if bare.startswith("#") or _MUTATES_UNLESS_FROZEN not in bare:
                        continue
                    if _FREEZE not in bare:
                        bad.append(f"{path.name} :: {job_name} :: "
                                   f"{step.get('name', '?')}\n      {bare[:110]}")
    return bad


def test_no_ci_step_lets_uv_relock_the_tree_it_judges() -> None:
    """`uv run` sans `--frozen` répare avant de juger."""
    bad = _unfrozen_uv_lines()
    assert not bad, (
        "ces étapes lancent `uv run` SANS `--frozen`. `uv run` re-verrouille et "
        "re-synchronise avant d'exécuter : une porte qui l'emploie corrige la dérive "
        "qu'elle est censée détecter, et rend vert un arbre qui ne l'est pas.\n"
        "Mesuré le 2026-09-16 : `Manifest consistency (blocking)` a laissé passer "
        "trois paquets divergents, et `uv.lock` était MODIFIÉ après son passage.\n  "
        + "\n  ".join(bad)
    )


def test_the_detector_sees_the_steps_it_claims_to_watch() -> None:
    """Non-vacuité : sans elle, un workflow renommé rendrait ce garde vert à vide."""
    steps = _steps_running_uv()
    assert len(steps) >= 5, (
        f"seulement {len(steps)} étape(s) employant `uv run` trouvée(s) — soit la CI "
        "a changé d'outil, soit la lecture du YAML est cassée. Dans les deux cas le "
        "test d'à côté ne garde plus rien."
    )
    # Et il DOIT savoir dire non : une ligne sans `--frozen` est attrapée.
    assert _FREEZE not in "uv run python x.py"
    assert _MUTATES_UNLESS_FROZEN in "uv run --frozen python x.py"
