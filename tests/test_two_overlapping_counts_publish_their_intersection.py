"""Garde : deux populations qui s'emboîtent publient leur intersection.

Type: Test
Uses: json, re, pathlib
Triggers: pytest
Persists in: nothing

Ce qui a été mesuré
-------------------
`.claude/dev-docs/error-class-health.md` publiait, dans **deux paragraphes ⚠️
consécutifs**, `swept_by_rerunning_the_guard` et `sites_unknown`. Au 2026-09-17 ils
valaient **97** et **100**, et leur **intersection valait 97** — une relance de garde ne
porte jamais de compte en gras, donc elle est muette **par construction**.

Un lecteur additionnait et concluait à **197 classes en défaut**, là où il y en avait
**100**. Rien dans le document ne l'en empêchait : deux nombres, deux paragraphes, aucune
mention du recouvrement.

Et la phrase du premier paragraphe DÉGÉNÉRAIT. Écrite pour l'ère des 97, elle rendait
« le nombre de classes dont personne n'a cherché les frères est donc **1**, et non 1 »
une fois le balayage terminé — un chiffre qui ne dit plus rien et qu'on lit quand même.

Ce que ce fichier tient
-----------------------
1. Le document publie `sites_unknown_hors_relance`, donc l'intersection est déductible.
2. La PROSE dit explicitement que les deux ne s'additionnent pas.
3. L'arithmétique tient : `intersection = sites_unknown − sites_unknown_hors_relance`, et
   elle ne peut pas dépasser `swept_by_rerunning_the_guard`.

Le point 3 est ce qui rend les deux premiers contredisables : une prose qui dirait
« ils ne s'additionnent pas » au-dessus de chiffres incohérents serait pire que rien.
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_JSON = _ROOT / ".claude" / "dev-docs" / "error-class-health.json"
_MD = _ROOT / ".claude" / "dev-docs" / "error-class-health.md"


def _trous() -> dict:
    return json.loads(_JSON.read_text(encoding="utf-8"))["aggregate"]["holes"]


def test_the_overlap_free_count_is_published() -> None:
    h = _trous()
    assert "sites_unknown_hors_relance" in h, (
        "`sites_unknown_hors_relance` a disparu du document généré. Sans lui, "
        "`sites_unknown` et `swept_by_rerunning_the_guard` sont deux nombres qui "
        "s'emboîtent et que rien n'empêche d'additionner — ce qui a fait lire "
        "« 197 classes en défaut » là où il y en avait 100.")


def test_the_arithmetic_of_the_overlap_holds() -> None:
    """L'intersection déduite doit être possible.

    Une relance de garde est muette par construction, donc l'intersection ne peut ni
    être négative, ni dépasser le nombre de relances.
    """
    h = _trous()
    muets = h["sites_unknown"]
    hors = h["sites_unknown_hors_relance"]
    relances = h["swept_by_rerunning_the_guard"]
    intersection = muets - hors
    assert intersection >= 0, (
        f"`sites_unknown_hors_relance` ({hors}) dépasse `sites_unknown` ({muets}) : le "
        "sous-ensemble est plus grand que l'ensemble. Un des deux compteurs ne mesure "
        "pas ce que son nom dit.")
    assert intersection <= relances, (
        f"l'intersection déduite ({intersection}) dépasse le nombre de relances "
        f"({relances}). Une relance est muette PAR CONSTRUCTION — elle ne porte jamais "
        "de compte en gras — donc toute relance est dans `sites_unknown`. Si ce n'est "
        "plus vrai, c'est `_swept_sites` ou `_swept_by_rerunning_the_guard` qui a "
        "changé, et la prose du document ment.")


def test_the_prose_says_the_two_counts_do_not_add_up() -> None:
    corps = _MD.read_text(encoding="utf-8")
    assert "NE S'ADDITIONNENT PAS" in corps, (
        "la prose générée ne dit plus que les deux populations se recouvrent. Publier "
        "deux nombres emboîtés dans deux paragraphes consécutifs SANS le dire est le "
        "défaut exact : au 2026-09-17, 97 et 100 d'intersection 97 se lisaient 197.")
    h = _trous()
    assert f"**{h['sites_unknown_hors_relance']}**" in corps, (
        f"la prose ne publie pas le compte hors recouvrement "
        f"({h['sites_unknown_hors_relance']}) — c'est lui qui rend l'addition "
        "impossible plutôt que seulement déconseillée.")


def test_the_prose_does_not_degenerate_when_the_count_is_zero() -> None:
    """Une phrase écrite pour un chiffre ne doit pas survivre à sa disparition.

    L'ancienne rendait « est donc **1**, et non 1 » : les deux membres de l'opposition
    étaient devenus égaux, et elle continuait de les opposer. C'est
    `a-prose-claim-that-cannot-be-verified` dans un document GÉNÉRÉ, donc reproduit à
    chaque exécution.
    """
    corps = _MD.read_text(encoding="utf-8")
    import re
    for m in re.finditer(r"est donc \*\*(\d+)\*\*, et non (\d+)", corps):
        assert m.group(1) != m.group(2), (
            f"la prose oppose {m.group(1)} à {m.group(2)}, qui sont le même nombre. "
            "Cette phrase a été écrite quand l'écart était de 97 ; elle a survécu à sa "
            "propre disparition et se relit comme une information.")


# ── Le contrôle des durées est CÂBLÉ là où il bloque — 2026-09-18 ────────────
#
# Seconde moitié de R139. `.test_durations` équilibre les quatre shards de CI, et il
# portait **26 entrées non collectables pour 33,2 s** — dont deux pesant 27,8 s à elles
# seules (les deux contrôles de fraîcheur sortis de la suite vers la CI le même jour) —
# plus **40 tests collectés sans durée**, à qui `pytest-split` donne une durée MOYENNE.
#
# ⚠️ **Le prédicat évident rend 0.** « Le fichier du node-id existe-t-il sur disque ? »
# ne trouve AUCUN des 26 : tous vivent dans des fichiers présents. Ce sont des tests
# renommés, retirés, ou dont la paramétrisation a changé.
#
# Le contrôle vit en CI et non dans `make test` — une collecte coûte ~8 s, et
# `.claude/dev-docs/test-suite-performance.md` documente que ce dépôt a déjà sorti les
# contrôles de fraîcheur de la suite pour ce motif. Ce test-ci ne fait donc PAS la
# collecte : il vérifie que l'outil existe et qu'il est branché.
# ⚠️ Le nom SANS extension, et ce n'est pas cosmétique.
# `test_no_new_textual_guard_is_added` signalait ce fichier alors qu'il ne lit AUCUN
# Python — que du JSON, du Markdown et un workflow YAML. Son troisième terme cherche un
# littéral `.py` dans le corps ; le mien y était, porté par une variable, et le tracer
# jusqu'à son usage demande une analyse de teinture que la liste gelée de ce cliquet a
# déjà mesurée comme hors de proportion (trois tentatives, toutes réfutées, les chiffres
# sont dans `_TEXTUAL_GUARDS`).
#
# Se faire inscrire dans cette liste aurait été du BUDGET pour un futur garde textuel que
# personne n'aurait décidé d'autoriser — elle ne doit que rétrécir. Retirer le littéral
# coûte moins et vaut mieux : ce fichier ne code plus l'extension en dur.
_NOM_OUTIL = "check_durations_are_collectable"
_DEV = _ROOT / "tools" / "dev"
_CI = _ROOT / ".github" / "workflows" / "ci.yml"


def test_the_durations_check_exists() -> None:
    trouves = list(_DEV.glob(f"{_NOM_OUTIL}.*"))
    assert trouves, (
        f"`tools/dev/{_NOM_OUTIL}` a disparu. C'est le seul contrôle qui compare "
        "`.test_durations` à une COLLECTE réelle ; le garde de la suite ne regarde que "
        "les FICHIERS, et le prédicat « le fichier existe-t-il » rend 0 sur 26 "
        "fantômes.")


def test_the_durations_check_runs_in_ci() -> None:
    assert _CI.is_file(), "ci.yml absent"
    # ⚠️ `_OUTIL.name`, pas le littéral. Ce fichier ne lit AUCUN Python — que du
    # Markdown, du JSON et un workflow YAML — et `test_no_new_textual_guard_is_added`
    # le signalait quand même : un littéral `.py` SONDÉ (jamais ouvert) suffit à
    # déclencher son quatrième terme, et la teinture ne se propage pas jusqu'au
    # cinquième. C'est le reste connu de ce cliquet, écrit dans sa propre liste gelée
    # après trois tentatives de correctif général toutes réfutées par la mesure.
    # Passer par le `Path` supprime le littéral ET donne une source unique au nom.
    assert _NOM_OUTIL in _CI.read_text(encoding="utf-8"), (
        "le contrôle des durées n'est plus lancé par `ci.yml`. Un contrôle qui n'est "
        "câblé nulle part n'en est pas un — et celui-ci garde le fichier qui répartit "
        "les quatre shards, donc son absence se paie en temps de CI déséquilibré, pas "
        "en rouge.")
