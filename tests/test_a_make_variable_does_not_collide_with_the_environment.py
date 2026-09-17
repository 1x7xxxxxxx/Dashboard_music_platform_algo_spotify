"""Une variable de `make` ne porte pas le nom d'une variable d'environnement standard.

Type: Test
Uses: re
Depends on: Makefile
Persists in: nothing

Le défaut
---------
`make` importe l'environnement dans ses variables. La cible `loadtest-concurrency`
lisait `$(USER)` pour l'option `--user` — or `USER` est une variable d'environnement
POSIX, valant ici `timothe`. `make loadtest-concurrency URL=…` sans autre argument
partait donc avec `--user timothe`, **silencieusement**.

Pourquoi ce n'est pas cosmétique sur cette cible précise
--------------------------------------------------------
Le mode authentifié « mesure une vraie page et **écrit dans `usage_events`** »
(docstring de `tools/loadtest_concurrency.py`). Une mesure de charge qui se croit
anonyme et qui écrit dans les données d'usage pollue exactement la table que
`tools/scale_check.sh` interroge pour décider s'il faut des répliques — c'est-à-dire
la décision que la mesure sert à éclairer.

Trouvé le 2026-09-17 en lançant la re-mesure R114 : la commande a affiché
`--user timothe` sans que personne ne l'ait demandé.

⚠️ Ce garde couvre les VARIABLES, pas les cibles. Un script appelé par une recette et
qui lirait `os.environ["USER"]` de son côté n'est pas vu.
"""
from __future__ import annotations

import re
from pathlib import Path

_MAKEFILE = Path(__file__).resolve().parents[1] / "Makefile"

# Variables que le shell exporte presque toujours. `make` les importe, donc
# `$(NOM)` y vaut la valeur de l'environnement, pas une absence.
# Source : POSIX + l'environnement d'un shell de connexion Linux courant.
_ENV_NAMES = frozenset({
    "USER", "HOME", "SHELL", "PATH", "PWD", "OLDPWD", "LANG", "LC_ALL", "TERM",
    "HOSTNAME", "LOGNAME", "EDITOR", "PAGER", "TMPDIR", "DISPLAY", "MAIL",
})

_REF = re.compile(r"\$\((\w+)\)")


def test_the_pattern_sees_the_makefile() -> None:
    """Non-vacuité : si plus aucune variable n'est référencée, ce test ne dit rien."""
    refs = set(_REF.findall(_MAKEFILE.read_text(encoding="utf-8")))
    assert len(refs) > 5, (
        f"le Makefile ne référence presque aucune variable ({sorted(refs)}) — "
        "ce garde ne démontre plus rien")


def test_no_make_variable_shadows_an_environment_variable() -> None:
    offenders = []
    for i, line in enumerate(_MAKEFILE.read_text(encoding="utf-8").splitlines(), 1):
        bare = line.lstrip()
        if bare.startswith("#") or bare.startswith("@#"):
            continue
        for name in _REF.findall(line):
            if name in _ENV_NAMES:
                offenders.append(f"Makefile:{i}: $({name})")
    assert not offenders, (
        "ces références prennent la valeur de l'ENVIRONNEMENT, pas une absence :\n  "
        + "\n  ".join(offenders) + "\n\n"
        "`make` importe l'environnement dans ses variables. `$(USER)` valait `timothe` "
        "et faisait basculer `loadtest-concurrency` en mode AUTHENTIFIÉ sans qu'on le "
        "demande — un mode qui ÉCRIT dans `usage_events`, la table même qui sert à "
        "décider s'il faut des répliques.\n"
        "Remède : un nom propre au projet (`LOGIN=`, `RUN_USER=`), jamais un nom POSIX.")
