#!/usr/bin/env python3
"""Chaque entrée de `.test_durations` désigne un test que pytest COLLECTE.

Type: Utility
Uses: json, subprocess, sys, pathlib
Triggers: .github/workflows/ci.yml
Persists in: nothing — lecture seule, sortie 0 ou 1

Pourquoi ce contrôle, et pourquoi PAS dans la suite
-----------------------------------------------------
`.test_durations` équilibre les six shards de CI. Une entrée qui ne désigne plus rien
gonfle la part d'un shard avec un temps qui ne sera jamais payé ; un test collecté sans
durée reçoit de `pytest-split` une durée MOYENNE — exactement ce que ce fichier existe
pour empêcher.

Mesuré le 2026-09-18 : **26 entrées non collectables pour 33,2 s**, dont deux à elles
seules pesaient **27,8 s (84 % de la masse)** — les deux contrôles de fraîcheur sortis de
la suite vers la CI le même jour. Et **40 tests collectés sans durée**.

⚠️ **Le prédicat ÉVIDENT rend 0.** « Le fichier du node-id existe-t-il sur disque ? » ne
trouve **aucun** des 26 : tous vivent dans des fichiers présents. Ce sont des tests
renommés, retirés, ou dont la paramétrisation a changé. La seule référence qui ne ment pas
est une COLLECTE réelle.

Ce contrôle vit en CI et non dans `make test` pour la raison que
`.claude/dev-docs/test-suite-performance.md` documente : une collecte coûte ~8 s, et ce
dépôt a déjà sorti de la suite les contrôles de fraîcheur pour ce motif exact. Le garde
`tests/test_the_shards_are_balanced_by_real_durations.py` reste dans la suite — il
surveille les FICHIERS, question moins chère et question différente.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DUR = _ROOT / ".test_durations"


def collection_errors(stdout: str) -> list[str]:
    """The test files pytest failed to import, from its `--collect-only -q` output."""
    return sorted({ligne.split()[1] for ligne in stdout.splitlines()
                   if ligne.startswith("ERROR tests/")})


def main() -> int:
    if not _DUR.is_file():
        print("❌ `.test_durations` absent — `pytest-split` répartirait sur le NOMBRE "
              "de tests. Remède : `make test-durations`.")
        return 1

    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:randomly",
         "--collect-only"],
        capture_output=True, text=True, cwd=str(_ROOT), timeout=600)
    collectes = {ligne.strip() for ligne in r.stdout.splitlines()
                 if "::" in ligne and ligne.strip().startswith("tests/")}

    if len(collectes) < 1000:
        print(f"❌ la collecte n'a rendu que {len(collectes)} test(s) — elle a échoué, "
              "et ce contrôle serait vert sur n'importe quel fichier de durées.\n"
              f"   code de sortie pytest : {r.returncode}\n"
              f"   {r.stdout[-400:]}")
        return 1

    # A file that fails to IMPORT is absent from the collection, so every duration it
    # owns reads as a phantom. On 2026-09-25 that is how a missing FERNET_KEY in this
    # job was reported: 37 "tests that no longer exist" in two files that exist.
    erreurs = collection_errors(r.stdout)
    if erreurs:
        print(f"❌ la collecte a échoué sur {len(erreurs)} fichier(s) — leurs durées "
              "passeraient pour des fantômes. Ce n'est pas `.test_durations` qui est "
              "faux, c'est l'environnement de ce job :")
        for f in erreurs:
            print(f"   {f}")
        print(f"\n{r.stdout[-1500:]}")
        return 1

    durees = json.loads(_DUR.read_text(encoding="utf-8"))
    fantomes = {k: v for k, v in durees.items() if k not in collectes}
    sans = sorted(collectes - set(durees))

    if not fantomes and not sans:
        print(f"▶ durations: {len(durees)} entrée(s), {len(collectes)} test(s) collecté(s)")
        print("✅ chaque durée désigne un test collecté, et chaque test a une durée")
        return 0

    if fantomes:
        masse = sum(fantomes.values())
        print(f"❌ {len(fantomes)} entrée(s) non collectable(s), {masse:.1f} s de temps "
              "attribué à des tests qui n'existent plus :")
        for k, v in sorted(fantomes.items(), key=lambda x: -x[1])[:10]:
            print(f"   {v:6.2f} s  {k}")
        if len(fantomes) > 10:
            print(f"   … et {len(fantomes) - 10} autre(s)")
    if sans:
        print(f"❌ {len(sans)} test(s) collecté(s) sans durée connue — `pytest-split` "
              "leur donne une durée MOYENNE :")
        for k in sans[:10]:
            print(f"   {k}")
        if len(sans) > 10:
            print(f"   … et {len(sans) - 10} autre(s)")
    print("\n   Remède : relancer les fichiers concernés EN SÉRIE avec "
          "`--store-durations` (pytest-split FUSIONNE sans `--clean-durations`), ou "
          "`make test-durations` pour tout régénérer.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
