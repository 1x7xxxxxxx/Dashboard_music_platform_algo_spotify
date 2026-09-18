"""Garde : l'alerte de dérive part même quand `src/` est inatteignable.

Type: Utility
Uses: subprocess, tempfile, pathlib
Triggers: pytest
Persists in: nothing

Classe d'erreur `a-guard-names-a-class-nobody-wrote` — ce fichier existe parce que
`tools/notify_schema_drift.py` NOMMAIT ce test dans trois `# pragma: no cover` et qu'il
n'existait pas. Un `grep -rn "test_alert_survives_a_broken_repo" tests/` ne rendait rien
le 2026-09-18 : trois replis d'import documentés comme couverts, zéro exécution.

Ce que le fichier gardé promet, dans sa propre prose (l. 24-31) :

> « ce script est le DERNIER maillon de l'alerte de dérive, et il ne doit pas dépendre
>   du paquet applicatif — un chemin d'import cassé ne doit jamais pouvoir faire taire
>   l'alerte. »

⚠️ **L'invariant était énoncé et faux dans le même fichier.** Jusqu'au 2026-09-18,
`from src.utils.env_files import load_project_env` était NU, dix lignes sous cette
phrase : un `src/` cassé tuait le script là, avant qu'aucun des replis ne s'exécute. La
prose décrivait une protection que le code ne portait pas, et rien ne le disait parce
que rien ne l'exerçait.

Le test simule l'état exact qu'il faut craindre : un arbre où `tools/` existe et où
`src/` **n'existe pas**. Il n'en simule pas l'idée — il copie le script, retire `src/`,
et regarde ce que le processus fait.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_OUTIL = _ROOT / "tools" / "notify_schema_drift.py"


def _arbre_sans_src(tmp: Path) -> Path:
    """Un dépôt réduit : le script, son dossier, et **aucun** `src/`."""
    (tmp / "tools").mkdir(parents=True)
    shutil.copy(_OUTIL, tmp / "tools" / _OUTIL.name)
    (tmp / ".env").write_text(
        "SMTP_HOST=smtp.invalid\nSMTP_PORT=587\nSMTP_USER=relay@invalid\n"
        "SMTP_PASSWORD=x\nALERT_EMAIL=ops@invalid\n", encoding="utf-8")
    return tmp


def _lancer(racine: Path, args: list[str], corps: str = "drift") -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("SMTP_", "ALERT_", "PYTHON"))}
    env["PATH"] = os.environ.get("PATH", "")
    return subprocess.run(
        [sys.executable, str(racine / "tools" / _OUTIL.name), *args],
        input=corps, capture_output=True, text=True, timeout=60, env=env, cwd=str(racine))


def test_the_alert_survives_a_broken_repo(tmp_path: Path) -> None:
    """Sans `src/`, le script DOIT aller jusqu'à sa décision d'envoi.

    Le critère n'est pas « il rend 0 » : sans relais SMTP joignable il ne peut pas
    livrer. C'est **qu'il ne meurt pas à l'import** — un `ModuleNotFoundError:
    src.utils.env_files` sur stderr est exactement le mode de panne que la prose du
    fichier déclare impossible.
    """
    racine = _arbre_sans_src(tmp_path)
    r = _lancer(racine, ["--subject", "TEST"])

    assert "ModuleNotFoundError" not in r.stderr, (
        "le script est mort à l'import alors que `src/` est absent — c'est le mode de "
        f"panne que sa propre prose déclare impossible.\nstderr:\n{r.stderr[:800]}")
    assert "Traceback" not in r.stderr, (
        f"le script a levé au lieu de décider.\nstderr:\n{r.stderr[:800]}")
    # Il a atteint la couche d'envoi : soit il annonce la non-configuration, soit il
    # rapporte un échec de livraison. Les deux prouvent qu'il a passé les imports.
    sortie = r.stdout + r.stderr
    assert ("email not configured" in sortie or "email send failed" in sortie
            or "emailed to" in sortie), (
        f"aucune décision d'envoi n'a été prise.\nstdout:\n{r.stdout[:400]}\n"
        f"stderr:\n{r.stderr[:400]}")


def test_a_broken_repo_still_loads_the_env_file(tmp_path: Path) -> None:
    """Le repli d'environnement charge vraiment `.env` — sinon il n'y a plus de relais.

    `load_project_env` vit dans `src/`. Quand il manque, le script a son propre
    chargeur. Sans lui, `SMTP_HOST` serait absent et la panne dirait « not configured »
    pour la mauvaise raison : on croirait le poste mal réglé alors que c'est le repli
    qui ne lit rien.
    """
    racine = _arbre_sans_src(tmp_path)
    r = _lancer(racine, ["--subject", "TEST"])
    sortie = r.stdout + r.stderr
    assert "email not configured" not in sortie, (
        "le repli n'a pas chargé `.env` : le script se croit non configuré alors que "
        f"les cinq variables y sont.\n{sortie[:600]}")


def test_the_broken_tree_really_has_no_src(tmp_path: Path) -> None:
    """Non-vacuité : sans cette vérification, les deux tests ci-dessus passeraient
    aussi bien sur un arbre où `src/` est présent — c'est-à-dire sans rien prouver."""
    racine = _arbre_sans_src(tmp_path)
    assert not (racine / "src").exists(), "l'arbre de test porte un `src/` — il ne simule rien"
    assert (racine / "tools" / _OUTIL.name).is_file()

# ⚠️ Un cinquième test a vécu ici pendant dix minutes, et les gardes du dépôt l'ont
# refusé le soir même — à raison. Il faisait
# `assert "test_the_alert_survives_a_broken_repo" in _OUTIL.read_text()` pour vérifier
# que les `# pragma: no cover` du script nomment bien ce fichier. Trois gardes l'ont
# attrapé d'un coup : `test_a_guard_reads_structure_not_text`,
# `test_no_new_assertion_compares_strings_against_source_text`, et surtout
# `test_a_presence_assertion_is_not_satisfied_by_prose`, qui a mesuré que l'assertion
# serait **DÉJÀ verte avec le code retiré** — elle était satisfaite par la prose du
# fichier qu'elle inspectait.
#
# La propriété qu'il visait est réelle : un `# pragma` qui nomme un test inexistant est
# exactement le défaut qui a créé ce fichier. Mais elle ne se garde pas en cherchant une
# chaîne dans un source, et la garder mal ici aurait appris que le rouge est du bruit.
# Elle est mesurée et consignée en R141, pas écrite ici : un balayage du flux de JETONS
# sur cinq arbres rend **196 citations de noms de tests dans des commentaires, dont 20
# orphelines** — et au moins l'une des 20 est une note de RETRAIT légitime
# (`test_a_step_is_offered_only_where_it_draws.py:152` dit « A ÉTÉ RETIRÉ LE
# 2026-09-13 », donc nommer le test retiré est exactement son travail). Le tri site par
# site est la tâche ; inventer le garde avant le tri crantait un chiffre faux.
