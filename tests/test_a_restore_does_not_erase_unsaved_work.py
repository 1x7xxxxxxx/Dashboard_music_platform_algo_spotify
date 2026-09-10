"""Un rétablissement git ne doit pas effacer du travail que rien ne rendra.

Type: Test
Uses: pytest, subprocess (le hook est un exécutable, pas un module)
Depends on: .claude/hooks/guard_destructive.py
Persists in: nothing (restaure chaque fichier qu'il salit)

Ce qui a été mesuré (2026-09-10)
--------------------------------
Le même geste a détruit du travail **deux fois dans la même séance**, à quelques heures
d'intervalle : rétablir un fichier depuis git pour défaire une mutation de test.

* la première fois : un correctif de rendu et deux clés i18n, non commités ;
* la seconde : la conversion de deux figures en petits multiples et l'élargissement d'un
  cliquet — et l'un des fichiers touchés était **gitignoré**, donc pas même restaurable
  par cette voie.

Entre les deux, j'avais écrit la leçon en mémoire. Elle n'a rien empêché : une leçon en
prose ne retient pas un geste réflexe. Ce qui l'a arrêtée est le geste de remplacement
(commiter avant de muter, `git stash` pour défaire) — et un geste ne se garde pas par une
note, il se garde par un hook.

Pourquoi le garde interroge l'état du dépôt au lieu d'interdire une chaîne
--------------------------------------------------------------------------
`git checkout -- .` et `git restore .` étaient déjà bloqués par correspondance de
chaîne. La forme qui coûte n'est pas celle-là : c'est la forme **chirurgicale**, sur un
fichier nommé, qui a l'air maîtrisée. Or sur un fichier propre, ce geste est un no-op
parfaitement légitime et d'usage courant — l'interdire par la chaîne rendrait le garde
insupportable, donc contourné.

Le garde lit donc `git status --porcelain` sur les chemins visés et ne bloque **que s'il
y a réellement quelque chose à perdre**, en le nommant. C'est la différence entre un
garde qu'on apprend à esquiver et un garde qui dit quelque chose de vrai.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "guard_destructive.py"

# Assemblé pour que ce fichier de test ne soit pas lui-même bloqué par le garde
# littéral qui cherche cette chaîne dans les commandes Bash.
_RESTORE_VERB = "git " + "checkout"

# Un fichier suivi, gros et inoffensif, qu'on salit puis qu'on rend.
_TARGET = "README.md"


def _hook(command: str) -> tuple[int, str]:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, cwd=str(ROOT), timeout=60)
    return r.returncode, (r.stdout or "")


@pytest.fixture
def dirty_target():
    """Salit un fichier suivi, le rend intact quoi qu'il arrive."""
    path = ROOT / _TARGET
    # BINAIRE, et pas `read_text`/`write_text`. Ce dépôt vit sur un montage Windows :
    # un aller-retour en mode texte réécrit les fins de ligne du fichier entier, et la
    # « restauration » laisse 52 lignes modifiées. Mesuré le 2026-09-10 en écrivant ce
    # test — la sonde censée vérifier qu'on n'abîme rien a abîmé sa propre cible.
    original = path.read_bytes()
    path.write_bytes(original + b"\n<!-- sonde du garde -->\n")
    try:
        yield _TARGET
    finally:
        path.write_bytes(original)


def test_a_clean_path_is_a_no_op_and_must_pass() -> None:
    """Interdire la forme rendrait le garde contournable ; il ne juge que la perte."""
    rc, _ = _hook(f"{_RESTORE_VERB} -- {_TARGET}")
    assert rc == 0, (
        "le garde bloque un rétablissement sur un fichier PROPRE, où il n'y a rien à "
        "perdre. Un garde qui interdit l'usage courant est un garde qu'on apprend à "
        "esquiver, et il ne protégera plus le jour où il aurait raison.")


def test_work_that_nothing_would_give_back_blocks_the_command(dirty_target) -> None:
    rc, out = _hook(f"{_RESTORE_VERB} -- {dirty_target}")
    assert rc == 2, (
        "un rétablissement sur un fichier PORTANT du travail non commité est passé : "
        "c'est exactement la commande qui a détruit deux correctifs le 2026-09-10")
    assert dirty_target in out, (
        "le garde bloque sans NOMMER ce qui serait perdu. Un refus sans inventaire "
        "oblige à deviner, et on redemande la même commande")
    assert "stash" in out, (
        "le message ne propose pas le geste de remplacement : un blocage sans "
        "alternative se contourne au lieu de changer l'habitude")


def test_git_restore_is_the_same_gesture(dirty_target) -> None:
    """Deux orthographes, un seul effet — en garder une seule serait la portée du défaut."""
    rc, _ = _hook(f"git restore {dirty_target}")
    assert rc == 2, "`git restore` détruit exactement la même chose et passait"


def test_staged_only_does_not_touch_the_working_tree(dirty_target) -> None:
    """`--staged` désindexe ; il ne peut rien effacer de l'arbre de travail."""
    rc, _ = _hook(f"git restore --staged {dirty_target}")
    assert rc == 0, (
        "le garde bloque `--staged`, qui ne touche pas l'arbre de travail — un faux "
        "positif sur un geste sans perte possible")


def test_the_gesture_is_seen_inside_a_compound_command(dirty_target) -> None:
    """Le geste voyage rarement seul ; il est souvent le second membre d'un `&&`."""
    rc, _ = _hook(f"echo bonjour && {_RESTORE_VERB} -- {dirty_target}")
    assert rc == 2, (
        "le garde ne lit que la tête de la commande : `… && <rétablissement>` est la "
        "forme la plus courante du geste, et elle passait")


def test_an_untracked_file_is_not_accused() -> None:
    """`checkout --` ne touche pas un fichier non suivi : l'accuser serait un faux positif."""
    probe = ROOT / "_probe_untracked_guard.txt"
    probe.write_bytes(b"sonde\n")
    try:
        rc, _ = _hook(f"{_RESTORE_VERB} -- {probe.name}")
        assert rc == 0, (
            "le garde accuse un fichier NON SUIVI, que ce geste ne peut pas toucher. "
            "Un garde qui crie sur ce qui ne risque rien perd sa crédibilité sur ce "
            "qui risque quelque chose")
    finally:
        probe.unlink(missing_ok=True)


def test_the_guard_never_raises_on_a_command_it_cannot_parse() -> None:
    """Ce hook précède CHAQUE appel Bash : une exception y bloquerait tout le travail."""
    for weird in (f"{_RESTORE_VERB} -- 'guillemet non fermé",
                  f"{_RESTORE_VERB} -- $(une substitution)",
                  "git restore",
                  f"{_RESTORE_VERB} -- /chemin/qui/n/existe/pas"):
        rc, _ = _hook(weird)
        assert rc in (0, 2), f"le hook a planté sur {weird!r} (rc={rc})"
