"""`make test` and CI must distribute the suite the same way.

Type: Test
Uses: re
Depends on: Makefile, .github/workflows/ci.yml
Persists in: nothing

Why this is worth a test
------------------------
Until 2026-08-30 CI ran `pytest -n auto --dist loadfile` and `make test` ran a plain
serial `pytest`. Two consequences, and the second is the expensive one:

* the local suite took 238 s where the same machine needed 151 s (measured);
* "green locally" and "green in CI" were not the same claim. This repo has already
  paid for that once: a caching defect stayed green in every local run and failed only
  on the runner.

`--dist loadfile` is not decoration. It keeps a file's tests on one worker, which is
what any test carrying module-level state depends on; plain `-n auto` scatters them and
turns such a test into a coin flip.

What this asserts
-----------------
Only that the two agree on the distribution flags. It does not pin the value: raising
or lowering parallelism is a legitimate decision — making it in ONE of the two places
is not.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_ROOT = Path(__file__).resolve().parents[1]
_MAKEFILE = _ROOT / "Makefile"
_CI = _ROOT / ".github/workflows/ci.yml"

_FLAGS = re.compile(r"(-n\s+\S+|--dist\s+\S+)")


def _ci_pytest_invocations() -> list[str]:
    """Les VRAIES invocations de la suite, lues dans les `run:` du YAML.

    Ceci lisait les lignes brutes du fichier et rendait la PREMIÈRE contenant
    « pytest tests/ ». Le 2026-09-16, un commentaire expliquant comment régénérer
    `.test_durations` a été ajouté au-dessus de la commande — il contient la même
    chaîne, sans aucun drapeau, et le garde a rougi en annonçant que la CI ne
    distribuait plus rien. Il avait tort, et il avait tort de la façon dont ce dépôt
    se trompe le plus souvent : en lisant du TEXTE là où la question est une
    STRUCTURE (`tests/test_a_guard_reads_structure_not_text.py`).

    On descend donc dans les `steps[].run` de chaque job, et on ignore les lignes de
    commentaire du script shell. Une matrice de shards rend plusieurs invocations —
    elles doivent TOUTES être d'accord avec le Makefile, pas seulement la première.
    """
    doc = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    found = []
    for job in doc.get("jobs", {}).values():
        for step in job.get("steps", []):
            for line in str(step.get("run", "")).splitlines():
                bare = line.strip()
                if bare.startswith("#") or "pytest tests/" not in bare:
                    continue
                found.append(bare)
    assert found, (
        "no `pytest tests/` invocation found in ci.yml — if CI stopped running the "
        "suite, that is the finding, not this test's bookkeeping."
    )
    return found


def _makefile_pytest_flags() -> set[str]:
    body = _MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^PYTEST_DIST\s*:?=\s*(.+)$", body, re.M)
    assert m, (
        "the Makefile no longer defines PYTEST_DIST. It exists so the local suite and "
        "CI cannot drift apart silently."
    )
    return set(_FLAGS.findall(m.group(1)))


def test_the_local_target_uses_the_pytest_dist_variable():
    body = _MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^test:.*?\n((?:\t.*\n)+)", body, re.M)
    assert m, "the Makefile has no `test:` target any more"
    assert "$(PYTEST_DIST)" in m.group(1), (
        "`make test` no longer passes $(PYTEST_DIST), so it can run the suite "
        "differently from CI without anything saying so."
    )


def _grouping(flags: set[str]) -> set[str]:
    """Ce qui change CE QUI est teste, par opposition a COMBIEN de processus le testent.

    ⚠️ Separe le 2026-09-17, et la distinction n'est pas un assouplissement.

    `--dist` decide du GROUPEMENT : avec `loadgroup`, les tests marques `xdist_group`
    tombent dans le meme worker. C'est une question de CORRECTION — deux fichiers qui
    ecrivent le meme locataire de la base partagee se marchent dessus autrement, et ce
    depot a eu deux rouges de cette forme le 2026-09-16. Un desaccord ici fait
    reellement dire deux choses differentes a « vert ».

    `-n N` ne decide que du DEBIT. Le meme ensemble de tests, les memes groupes, sur
    plus ou moins de processus.

    Ce qui a force la separation : `make test` a ete **tue par l'OOM deux fois** en une
    heure, a `-n auto` puis a `-n 6`. Ce poste porte `n8n-ollama` (2,53 Go) et le serveur
    MCP `knowledge-rag` (1,15 Go) en permanence ; un runner GitHub n'a ni l'un ni
    l'autre. Exiger le MEME nombre de workers des deux cotes, c'est exiger qu'un des
    deux se fasse tuer — et une suite tuee rend un journal VIDE, qui se lit comme
    « rien ne tourne ».

    Le garde continue donc d'exiger l'accord sur `--dist`, et n'exige plus rien sur
    `-n`. Ce qu'on perd est reel et borne : un ecart de PARALLELISME ne sera plus
    signale. Ce qu'on garde est ce qui rendait le garde utile.
    """
    return {f for f in flags if f.startswith("--dist")}


def test_the_two_agree_on_how_the_suite_is_distributed():
    local = _makefile_pytest_flags()
    for invocation in _ci_pytest_invocations():
        ci = set(_FLAGS.findall(invocation))
        assert _grouping(ci) == _grouping(local), (
            f"CI groupe la suite avec {sorted(_grouping(ci))} et `make test` avec "
            f"{sorted(_grouping(local))}.\n"
            f"  invocation : {invocation}\n"
            "`--dist` decide de CE QUI est teste ensemble : avec `loadgroup`, les tests "
            "marques `xdist_group` tiennent sur le meme worker. Un desaccord ici fait "
            "dire deux choses differentes a « vert », et ce depot a deja livre un defaut "
            "que seul le runner voyait.\n"
            "Changer les deux, ou aucun."
        )


def test_both_sides_still_declare_a_worker_count():
    """`-n` n'a plus besoin d'etre EGAL, mais il doit exister des deux cotes.

    Sans cette assertion, la separation ci-dessus laisserait passer une CI qui perd
    `-n` entierement et retombe en serie — 1 146 s contre 418 s mesurees, et personne
    ne le verrait puisque plus rien ne compare les deux.
    """
    local = _makefile_pytest_flags()
    assert any(f.startswith("-n") for f in local), (
        "le Makefile ne declare plus de nombre de workers — la suite locale retombe "
        "en serie, mesuree a 2,74x le temps"
    )
    for invocation in _ci_pytest_invocations():
        ci = set(_FLAGS.findall(invocation))
        assert any(f.startswith("-n") for f in ci), (
            f"cette invocation CI ne declare plus de workers : {invocation}"
        )


def test_the_extraction_ignores_a_comment_that_mentions_the_command():
    """Non-vacuité : sans elle, un extracteur cassé rendrait ce fichier vert à vide.

    Les deux directions sont épinglées — il voit une vraie commande, et il ne voit
    pas un commentaire qui la décrit.
    """
    invocations = _ci_pytest_invocations()
    assert invocations, "aucune invocation trouvée"
    assert all(not i.startswith("#") for i in invocations)
    assert all(_FLAGS.findall(i) for i in invocations), (
        f"une invocation sans aucun drapeau de distribution : {invocations}"
    )
    # Et le fichier contient bien au moins un commentaire piégeur, sinon
    # l'assertion ci-dessus ne prouve rien de ce qu'elle prétend.
    raw = _CI.read_text(encoding="utf-8")
    pieges = [ln.strip() for ln in raw.splitlines()
              if "pytest tests/" in ln and ln.strip().startswith("#")]
    assert pieges, (
        "ci.yml ne contient plus de commentaire mentionnant `pytest tests/` : ce test "
        "de non-vacuité ne démontre plus rien. Le retirer, ou remettre le piège."
    )
