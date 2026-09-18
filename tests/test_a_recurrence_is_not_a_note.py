"""Une ligne d'`History` ne compte comme récidive que si elle le DIT.

Type: Test
Uses: importlib
Depends on: tools/dev/error_class_health.py, .claude/dev-docs/error-classes.md
Persists in: nothing

Jusqu'au 2026-09-18, `history_additions` comptait **toute** ligne d'`History` ajoutée
à une classe. Les 81 lignes concernées ont été classées une par une :

  * **33** sont de vraies récidives — le défaut est réapparu sur un site neuf ;
  * **26** sont des défauts du GARDE — signature dérivée, prédicat aveugle, faux positif ;
  * **22** sont du travail sur la classe — garde ajouté, statut changé, verdict de balayage.

Le compteur les additionnait, donc le taux de récidive — le chiffre sur lequel repose
l'argument « une classe sans garde automatique récidive N× plus », cité dans `CLAUDE.md`
et dans ce fichier — était surestimé d'un facteur **2,5**. Le mode d'échec est le pire
possible pour une mesure : **écrire le verdict d'un balayage qui PROUVE qu'une classe est
saine faisait monter sa récidive.** Mesuré le jour même : deux balayages à zéro site
vivant ont porté `ever_recurred_observed` de 54 à 56.

Ce que ce garde fixe
--------------------
1. Une ligne **non marquée** n'est pas un évènement.
2. Une ligne `(récidive)` en est un.
3. Une ligne `(garde)` n'en est pas un — elle est comptée à part.
4. Anti-vacuité : le catalogue en porte réellement, sinon tout ce fichier passe à vide.

Ce qu'il ne couvre PAS
----------------------
Que la marque soit JUSTE. Classer une ligne reste un jugement humain ; ce garde vérifie
que le compteur honore la marque, pas que la marque dise vrai. Le rétro-marquage des 81
lignes est tracé dans le message de commit du 2026-09-18.

Mutation record — 2026-09-18 : (1) faire compter les lignes non marquées → rouge ;
(2) faire compter `(garde)` comme une récidive → rouge ; (3) rendre le catalogue muet
(aucune marque) → rouge sur l'anti-vacuité.

---
rex: []
---
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_CAT = _ROOT / ".claude" / "dev-docs" / "error-classes.md"


def _sante():
    spec = importlib.util.spec_from_file_location(
        "_ech", _ROOT / "tools" / "dev" / "error_class_health.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _compte(mod, corps: str) -> tuple[int, int]:
    """(récidives, défauts de garde) — par la FONCTION du module, jamais par sa regex.

    La première version de ce garde recomposait le calcul ici à partir de
    `_HISTORY_MARKED`. Il est resté VERT quand on a rendu le compteur permissif, parce
    qu'il n'appelait pas le compteur. C'est le défaut que ce fichier documente, commis
    dans le fichier qui le documente.
    """
    recid, gardes, _muettes = mod._events(corps)
    return recid, gardes


def test_the_catalogue_actually_carries_marks() -> None:
    """Anti-vacuité : sans marque, les trois tests suivants passent sur du vide."""
    mod = _sante()
    marques = mod._HISTORY_MARKED.findall(_CAT.read_text(encoding="utf-8"))
    rec = sum(1 for _d, k in marques if k == "récidive")
    gar = sum(1 for _d, k in marques if k == "garde")
    assert rec >= 20 and gar >= 15, (
        f"{rec} récidives et {gar} défauts de garde marqués dans le catalogue — il y en "
        "avait 32 et 26 le 2026-09-18. Sous ce seuil, le rétro-marquage a été perdu et "
        "le compteur est revenu à « toute ligne compte », en silence.")


def test_an_unmarked_line_is_not_an_event() -> None:
    mod = _sante()
    corps = ("- History:\n"
             "  - 2026-09-18: balayée, 0 site vivant. Le verdict d'un balayage sain.\n"
             "  - 2026-09-17: `guarded`. Garde ajouté.\n")
    assert _compte(mod, corps) == (0, 0), (
        "une note de travail est comptée comme une récidive — c'est exactement le "
        "défaut corrigé le 2026-09-18 : écrire qu'une classe est saine la faisait "
        "paraître récidiviste.")


def test_a_marked_recurrence_is_an_event() -> None:
    mod = _sante()
    corps = ("- History:\n"
             "  - 2026-09-18 (récidive): le défaut est réapparu sur un site neuf.\n")
    assert _compte(mod, corps) == (1, 0)


def test_a_guard_failure_is_counted_apart() -> None:
    """Un garde pris aveugle n'est pas le défaut qui revient."""
    mod = _sante()
    corps = ("- History:\n"
             "  - 2026-09-18 (garde): la signature était ancrée sur un numéro de ligne.\n")
    rec, gar = _compte(mod, corps)
    assert (rec, gar) == (0, 1), (
        "un défaut du GARDE est compté comme une récidive de la CLASSE. Les deux "
        "appellent des remèdes opposés : l'un demande d'élargir le garde, l'autre de "
        "chercher d'autres sites. Les confondre, c'est perdre les deux signaux.")


def test_the_plain_history_regex_still_sees_marked_lines() -> None:
    """Le lecteur de DATES doit lire les deux formes, sinon les dates disparaissent."""
    mod = _sante()
    corps = ("  - 2026-09-18 (récidive): a\n"
             "  - 2026-09-17 (garde): b\n"
             "  - 2026-09-16: c\n")
    assert sorted(mod._HISTORY_LINE.findall(corps)) == [
        "2026-09-16", "2026-09-17", "2026-09-18"], (
        "`_HISTORY_LINE` ne reconnaît plus une ligne marquée : les dates déclarées "
        "d'une classe disparaîtraient du document au moment où on la marque.")
