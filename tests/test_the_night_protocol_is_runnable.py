"""Le protocole de séance longue nomme des commandes ; elles doivent exister.

Type: Utility
Uses: subprocess, tools/dev/night_run.py
Triggers: pytest
Persists in: nothing

Error class `a-runbook-that-names-a-command-nobody-can-run`.

Un protocole est lu à 3 h du matin par quelqu'un — ou quelque chose — qui ne peut
demander à personne. Une commande qui n'existe plus s'y lit comme une commande qui
marche : c'est la forme la plus chère d'une doc périmée, parce qu'elle ne se signale
qu'au moment où on s'y fie.

Ce dépôt a la mesure : `.claude/skills/impact-analysis/SKILL.md` a été nommé par la règle
transverse #11 pendant des semaines alors que le fichier n'existait pas, et rien ne
l'a dit. Le protocole de nuit est exactement ce genre de fichier — rarement relu, et
suivi littéralement quand il l'est.

Mutation record — 2026-09-16, vue rouge : `night-status` renommé en `night-statuz`
dans le protocole → `test_every_make_target_the_protocol_names_exists` rouge en
nommant la cible ; remis, vert. Seconde mutation : la cible `night-check` retirée du
`Makefile` → même test rouge, ce qui est le point (le protocole et le `Makefile`
doivent bouger ensemble, dans les deux sens).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PROTOCOL = REPO / ".claude" / "dev-docs" / "roadmap" / "night-run.md"
SCRIPT = REPO / "tools" / "dev" / "night_run.py"
MAKEFILE = REPO / "Makefile"

_MAKE_CALL = re.compile(r"\bmake\s+(night-[a-z-]+)")


def _named_targets() -> set[str]:
    return set(_MAKE_CALL.findall(PROTOCOL.read_text(encoding="utf-8")))


def _declared_targets() -> set[str]:
    return set(re.findall(r"^(night-[a-z-]+):", MAKEFILE.read_text(encoding="utf-8"),
                          re.M))


def test_the_protocol_and_the_script_are_both_there() -> None:
    assert PROTOCOL.exists(), "le protocole de séance longue a disparu"
    assert SCRIPT.exists(), "night_run.py a disparu — le protocole ne peut plus tourner"


def test_the_protocol_stays_readable_in_one_sitting() -> None:
    """Il promet « une page » ; un protocole qu'on ne relit pas n'existe pas."""
    size = PROTOCOL.stat().st_size
    assert size <= 8192, (
        f"night-run.md fait {size} octets. Il est lu à CHAQUE réveil : son poids se "
        "paie à chaque fois. Ce qui grossit va dans la roadmap ou dans une classe "
        "d'erreur, pas ici.")


def test_every_make_target_the_protocol_names_exists() -> None:
    named, declared = _named_targets(), _declared_targets()
    assert named, "aucune cible `make night-*` citée — le parseur regarde à côté"
    missing = sorted(named - declared)
    assert not missing, (
        f"le protocole dit de lancer {missing}, absent(e) du Makefile. Une commande "
        "qui n'existe plus se lit comme une commande qui marche.")


def test_every_declared_target_is_explained_somewhere() -> None:
    """L'autre sens. Une cible que rien ne documente ne sera jamais lancée.

    C'est la réciproque du test précédent, et ce dépôt vient de payer l'absence d'une
    réciproque : sept gardes nommaient une classe d'erreur inexistante parce que la
    cohérence n'était vérifiée que dans un sens (`a-guard-names-a-class-nobody-wrote`).
    """
    text = PROTOCOL.read_text(encoding="utf-8")
    orphan = sorted(t for t in _declared_targets() if t not in text)
    assert not orphan, (
        f"{orphan} existe(nt) dans le Makefile et n'apparaî(ssen)t pas dans le "
        "protocole — donc rien ne les lancera jamais.")


@pytest.mark.parametrize("sub", ["status", "check", "start", "done", "park", "note"])
def test_every_subcommand_the_makefile_uses_is_accepted(sub: str) -> None:
    """Le `Makefile` appelle le script ; le script doit connaître ces sous-commandes."""
    out = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                         capture_output=True, text=True, timeout=30)
    assert sub in out.stdout, f"`{sub}` n'est plus une sous-commande de night_run.py"


def test_status_runs_and_answers_the_question_it_promises() -> None:
    """Non-vacuité : il doit sortir 0 ET porter les quatre rubriques annoncées."""
    out = subprocess.run([sys.executable, str(SCRIPT), "status"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-500:]
    for heading in ("EN COURS", "ARBRE", "ROADMAP", "JOURNAL"):
        assert heading in out.stdout, (
            f"`status` ne rend plus la rubrique {heading!r} — c'est la commande qui "
            "répond « où j'en suis » après une compaction, ses rubriques sont son "
            "contrat.")


def test_the_probe_does_not_see_its_own_shell() -> None:
    """Le piège dans lequel ce fichier est tombé en s'écrivant.

    La première version cherchait « pytest » et « tests/ » dans le `cmdline` APLATI :
    le shell qui exécutait la sonde portait les deux mots, donc `status` annonçait
    « une suite tourne » en permanence. `a-kill-pattern-that-matches-its-own-shell`.

    Ici le test EST lancé par pytest sur `tests/`, donc la sonde a toutes les raisons
    de se voir elle-même — c'est le meilleur endroit du dépôt pour poser la question.
    Un vrai `pytest tests/…` tourne : la sonde doit le voir SANS se compter.
    """
    sys.path.insert(0, str(SCRIPT.parent))
    import night_run  # noqa: PLC0415 — chargé tardivement, il n'est pas un paquet

    assert night_run._ancestors(), "la lignée du processus est vide — /proc illisible ?"
    # Le processus courant EST un pytest sur tests/ ; il doit être exclu de sa lignée,
    # donc la sonde ne doit pas le compter comme « une autre suite ».
    import os
    assert os.getpid() in night_run._ancestors()
