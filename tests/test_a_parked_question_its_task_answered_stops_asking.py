"""Une question parquée que sa propre tâche a tranchée cesse d'être posée.

Type: Test
Uses: tools.dev.night_run
Depends on: tools/dev/night_run.py
Persists in: nothing

Le défaut
---------
`night-status` listait TOUS les `park` du journal, sans jamais les retirer. R117 a été
parquée le 2026-09-17 au matin — « déplacer le dépôt tue la session qui le fait » — puis
LIVRÉE le même jour, et l'écran a continué de poser la question. Un écran de reprise est
la première chose qu'on lit après une compaction : y affirmer un blocage résolu envoie
chercher une décision déjà prise.

Famille `un-document-qui-affirme-un-état-périmé`.

Ce qui est gardé, et ce qui ne l'est pas
---------------------------------------
Le critère est l'ORDRE, pas la présence. Un `done` postérieur referme la question ; un
`park` postérieur à un `done` la rouvre — c'est le cas d'une tâche reprise puis bloquée
à nouveau, et il doit continuer de s'afficher.

⚠️ Ce garde ne dit rien des questions parquées d'une tâche qu'on a ABANDONNÉE sans
`done` : le journal n'a pas de verbe pour ça, elles resteront affichées. C'est un trou
connu, pas un oubli.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MOD = Path(__file__).resolve().parents[1] / "tools" / "dev" / "night_run.py"


def _parked(entries: list[dict]) -> list[dict]:
    """Appelle la VRAIE fonction du module.

    ⚠️ La première version de ce fichier rejouait une COPIE de la règle ici. Muter
    `night_run.py` laissait les trois tests de comportement VERTS — seul le contrôle
    textuel rougissait. C'est le défaut que ce fichier est censé garder, commis dans
    le garde lui-même. On importe, on ne réimplémente pas.
    """
    spec = importlib.util.spec_from_file_location("_night_run_under_test", _MOD)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.open_questions(entries)


def test_a_park_followed_by_its_done_stops_asking() -> None:
    """Le défaut exact : R117, parquée puis livrée le même jour."""
    journal = [
        {"kind": "park", "task": "R117", "what": "déplacer le dépôt tue la session"},
        {"kind": "done", "task": "R117", "what": "deux moitiés livrées"},
    ]
    assert _parked(journal) == []


def test_a_park_that_nothing_answered_keeps_asking() -> None:
    """R116 attend de la donnée, pas un geste : elle doit rester affichée."""
    journal = [{"kind": "park", "task": "R116", "what": "ADR-027 attend 14 jours"}]
    assert [e["task"] for e in _parked(journal)] == ["R116"]


def test_a_park_after_a_done_reopens_the_question() -> None:
    """L'ORDRE compte : une tâche reprise puis rebloquée repose sa question.

    Sans ce cas, « la tâche a un done quelque part » suffirait — et une tâche livrée
    puis rouverte et bloquée à nouveau disparaîtrait de l'écran en silence.
    """
    journal = [
        {"kind": "done", "task": "R42", "what": "livrée"},
        {"kind": "park", "task": "R42", "what": "rouverte, puis bloquée"},
    ]
    assert [e["task"] for e in _parked(journal)] == ["R42"]
