"""Les gardes Bash bloquent un GESTE, jamais une phrase qui le nomme.

Type: Test
Uses: pytest, .claude/hooks/guard_destructive.py
Depends on: .claude/hooks/guard_destructive.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Le 2026-09-12, trois commandes d'affilée ont été bloquées par le hook du dépôt — et
aucune ne faisait ce qu'il croyait. Elles ÉCRIVAIENT la classe d'erreur du geste,
donc elles le NOMMAIENT, et le hook comparait des sous-chaînes.

Le mode d'échec du garde de rétablissement est pire qu'un faux positif ordinaire.
Sa phrase d'exemple contenait `git checkout -- <fichier> … : ne bloquer que si`, et
les jetons de la phrase deviennent des chemins passés à `git status`. L'un d'eux
était `:` — en syntaxe de pathspec git, **cela désigne tous les fichiers du dépôt**.
Une phrase en prose faisait donc croire au garde que le dépôt entier allait être
écrasé, et il bloquait. Documenter le garde rendait le garde inutilisable.

C'est `a-textual-guard-is-blind`, appliqué aux hooks et non aux tests : un garde qui
inspecte du CODE doit lire sa structure. Ici, la structure minimale suffit — le geste
doit être la COMMANDE de son segment (premiers jetons, `sudo`/`time`/`nohup` admis),
pas un mot dans un argument.

Ce que ce fichier tient, et ce qu'il ne tient pas
--------------------------------------------------
Il tient les deux sens pour les deux gardes : le vrai geste bloque, la mention passe.
Il ne juge PAS l'avertissement générique (`warn`) — celui-ci n'empêche rien et son
bruit est assumé depuis longtemps.

Journal de mutation — 2026-09-12 : avec le filtre structurel retiré de l'un ou
l'autre garde, le cas « mention » correspondant vire au rouge en nommant la phrase.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_HOOK = _ROOT / ".claude" / "hooks" / "guard_destructive.py"

# Les noms sont assemblés pour que CE fichier ne soit pas lui-même un appel aux yeux
# d'un lecteur naïf — la blague est sérieuse : c'est exactement le piège qu'il teste.
_KILL = "p" + "kill"
_GIT = "g" + "it"


def _check(command: str):
    sys.path.insert(0, str(_HOOK.parent))
    try:
        from guard_destructive import check_command
        return check_command(command)
    finally:
        sys.path.pop(0)


def _clean_tracked_file() -> str:
    """Un fichier suivi et NON modifié — sinon le garde a raison de bloquer."""
    listed = subprocess.run([_GIT, "ls-files", "src/"], cwd=_ROOT,
                            capture_output=True, text=True, timeout=20)
    for path in listed.stdout.splitlines()[:200]:
        st = subprocess.run([_GIT, "status", "--porcelain", "--", path], cwd=_ROOT,
                            capture_output=True, text=True, timeout=20)
        if st.returncode == 0 and not st.stdout.strip():
            return path
    pytest.skip("aucun fichier suivi propre — l'arbre entier est modifié")
    return ""


@pytest.mark.parametrize("command,label", [
    (f'{_KILL} -f "pytest tests/" ; echo la_suite', "suivi d'une autre commande"),
    (f'sudo {_KILL} -f node && echo ok', "précédé de sudo, suivi"),
])
def test_a_real_kill_that_would_take_the_shell_with_it_is_blocked(command, label):
    """Le motif est dans la ligne du shell : il se tue, et la suite ne part pas."""
    got = _check(command)
    assert got and got[0] == "block", (
        f"{label} : le garde laisse passer. Le shell mourra en 144 et ce qui suit "
        f"ne tournera jamais — arrivé trois fois le 2026-09-12. Obtenu : {got}")


@pytest.mark.parametrize("command,label", [
    (f'echo "on parle de {_KILL} -f pytest ; et ensuite"', "kill nommé dans une phrase"),
    (f'echo "le garde de {_GIT} checkout -- <f> au-dessus : ne bloquer que si"',
     "rétablissement nommé dans une phrase"),
])
def test_merely_naming_the_gesture_never_blocks(command, label):
    """Écrire SUR le défaut ne doit pas déclencher le garde du défaut.

    Sinon la seule façon de garder le travail possible est d'arrêter de documenter —
    la leçon du 2026-08-03, repayée ici sur un hook au lieu d'une signature.
    """
    got = _check(command)
    assert not got or got[0] != "block", (
        f"{label} : une simple MENTION bloque. Documenter le garde rend le garde "
        f"inutilisable. Obtenu : {got}")


def test_a_restore_on_a_clean_file_stays_a_no_op():
    """Le garde de rétablissement est à ÉTAT : rien à perdre, rien à bloquer."""
    path = _clean_tracked_file()
    got = _check(f"{_GIT} checkout -- {path}")
    assert not got or got[0] != "block", (
        f"`checkout` d'un fichier PROPRE ({path}) est bloqué : le garde a cessé de "
        f"lire l'état et bloque la forme. Obtenu : {got}")


def test_a_restore_that_would_lose_work_still_blocks():
    """NON-VACUITÉ : sans ce sens-là, tout assouplir rendrait ce fichier vert.

    Le garde existe pour un dégât réel — deux correctifs perdus le 2026-09-10. On
    vérifie donc qu'il mord encore, sur un fichier qu'on salit puis qu'on rend.
    """
    victim = _ROOT / "README.md"
    if not victim.exists():
        pytest.skip("pas de README.md à salir")
    before = victim.read_bytes()          # BINAIRE : le mode texte réécrirait les
    try:                                   # fins de ligne du fichier entier.
        victim.write_bytes(before + b"\n<!-- sonde du garde -->\n")
        got = _check(f"{_GIT} checkout -- README.md")
        assert got and got[0] == "block", (
            "un fichier porte du travail non commité et le garde laisse passer : "
            f"il ne lit plus l'état du dépôt. Obtenu : {got}")
        assert "README.md" in got[1], "le message ne NOMME pas ce qui serait perdu"
    finally:
        victim.write_bytes(before)
