"""Garde : un commentaire qui renvoie à un fichier de test nomme un fichier qui existe.

Type: Test
Uses: io, tokenize, pathlib
Triggers: pytest
Persists in: nothing

R141, mesurée le 2026-09-18.

Le chiffre de la roadmap était un PLAFOND, et il valait 7×
-----------------------------------------------------------
L'entrée annonçait **20 citations orphelines** — des noms de tests nommés dans un
commentaire et définis nulle part. Triées une par une :

* **15 sont des notes de RETRAIT légitimes.** Un commentaire qui dit « `test_x` A ÉTÉ
  RETIRÉ LE 2026-09-13 » nomme `test_x` : c'est son travail. En compter une comme un
  défaut punit la seule pratique qui rende un retrait traçable.
* **2 sont des faux positifs du prédicat** : `test_ok_account` venait de la clé de
  traduction `credentials.meta.test_ok_account`, et `test_durations` du FICHIER
  `.test_durations`. Ni l'un ni l'autre n'est un nom de test.
* **3 sont de vrais pointeurs morts**, et les trois nomment un FICHIER :
  `tests/test_claude_config.py` (renommé en `…_floor.py`),
  `tests/test_rex_covers_every_injectable.py` (n'a jamais existé — le garde vit dans
  `test_no_rex_lives_outside_the_validator.py`, et **autrement** que le commentaire
  l'annonçait), et
  `tests/test_the_defect_gauge_is_installed_once_and_only_by_the_dashboard.py` (le garde
  vit dans `test_the_api_measures_itself_without_unbounded_labels.py:118-122`).

**20 → 3**, facteur ~7, et toujours dans le sens du sur-comptage — la neuvième fois de la
séance. Aucune de ces corrections n'est venue d'une relecture du prédicat : toutes sont
venues de la lecture site par site.

Ce que ce fichier garde, et ce qu'il ne garde PAS
--------------------------------------------------
Il contraint les renvois à un **FICHIER** (`tests/…py`) — la forme des trois vrais
défauts, et celle qu'on peut vérifier sans ambiguïté. Il ne contraint pas les noms de
FONCTIONS cités en prose : un nom de fonction survit légitimement dans une note de
retrait, et les distinguer demanderait de juger l'intention d'un commentaire.

Le renvoi EST la contrainte. Un commentaire qui ne nomme aucun chemin n'est pas concerné,
donc ce garde ne peut pas pousser à retirer un renvoi pour se taire.
"""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_ARBRES = ("tests", "tools", "src", "airflow", ".claude/scripts", ".claude/hooks")
# `tests/<nom>.py`, éventuellement suivi de `::<fonction>` ou d'un `:<ligne>`.
_RENVOI = re.compile(r"\btests/(test_[a-z0-9_]+)\.py\b")


def _citations() -> list[tuple[str, int, str]]:
    """`(fichier, ligne, nom)` pour chaque renvoi à un fichier de test, dans un COMMENTAIRE.

    Les commentaires sont lus par `tokenize`, donc en tant que commentaires — pas par une
    recherche de texte qui attraperait aussi le code et les chaînes.
    """
    out = []
    for arbre in _ARBRES:
        base = _ROOT / arbre
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.py")):
            if "__pycache__" in str(f):
                continue
            try:
                toks = tokenize.generate_tokens(
                    io.StringIO(f.read_text(encoding="utf-8")).readline)
                for tok in toks:
                    if tok.type != tokenize.COMMENT:
                        continue
                    for m in _RENVOI.finditer(tok.string):
                        out.append((str(f.relative_to(_ROOT)), tok.start[0], m.group(1)))
            except (SyntaxError, tokenize.TokenError, UnicodeDecodeError):
                continue
    return out


def test_the_citation_extraction_is_not_vacuous() -> None:
    """Sans extraction, l'assertion suivante est verte sur un dépôt entièrement faux."""
    cit = _citations()
    assert len(cit) >= 10, (
        f"seulement {len(cit)} renvoi(s) à un fichier de test extrait(s) des "
        "commentaires — l'extraction a raté sa cible. Ce dépôt en porte des dizaines.")


@pytest.mark.parametrize("fichier,ligne,nom", _citations() or [("(aucun)", 0, "")],
                         ids=lambda v: str(v)[:60])
def test_a_comment_names_a_test_file_that_exists(fichier: str, ligne: int, nom: str) -> None:
    if fichier == "(aucun)":
        pytest.skip("aucun renvoi extrait")
    cible = _ROOT / "tests" / f"{nom}.py"
    assert cible.is_file(), (
        f"{fichier}:{ligne} renvoie à `tests/{nom}.py`, qui n'existe pas.\n\n"
        "Un renvoi qui manque ne se plaint pas : il envoie chercher. Trois l'ont fait "
        "jusqu'au 2026-09-18, dont un vers un fichier qui n'a JAMAIS existé et un autre "
        "qui décrivait un mécanisme que le garde réel n'emploie pas.\n"
        "Corriger le chemin, ou — si le test a été retiré — le dire dans le commentaire "
        "plutôt que de le nommer comme s'il existait encore.")
