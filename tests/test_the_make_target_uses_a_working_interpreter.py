"""La cible `make test` doit lancer un interpréteur capable de charger `conftest.py`.

Type: Test
Uses: pytest, subprocess, re
Depends on: Makefile, tests/conftest.py
Persists in: nothing

Ce qui a été mesuré (2026-09-15)
--------------------------------
`make test` ne lançait **aucun test**. `PYTHON` était figé sur
`venv/Scripts/python.exe`, le venv Windows, qui ne porte pas `pytest-xdist` ; le
hook `pytest_configure_node` déclaré dans `tests/conftest.py` y est donc un hook
INCONNU, `pluggy` lève `PluginValidationError`, et pytest sort en `INTERNALERROR`
avec `rc=3` et « no tests ran in 0.05s ».

Ce n'est pas un silence — le code de retour est non nul — mais il ne ressemble pas
à un échec de test, sur la cible même qu'on lance pour ne pas lire la sortie en
détail. La suite pouvait donc être « lancée » sans rien prouver.

Ce que ce garde vérifie, et ce qu'il ne vérifie pas
--------------------------------------------------
Il vérifie l'**effet** : l'interpréteur que le Makefile a résolu peut-il réellement
collecter dans `tests/` ? Il ne vérifie pas quel chemin est écrit dans le fichier —
un chemin peut être parfaitement lisible et pointer un interpréteur incapable, et
c'est exactement ce qui est arrivé.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = REPO / "Makefile"


def _resolved_python() -> str:
    """L'interpréteur que `make` utiliserait réellement, résolu par `make` lui-même."""
    r = subprocess.run(["make", "-n", "test"], cwd=REPO,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        pytest.skip(f"`make -n test` indisponible ici : {r.stderr.strip()[:120]}")
    for line in r.stdout.splitlines():
        m = re.search(r"(\S*python\S*)\s+-m\s+pytest", line)
        if m:
            return m.group(1)
    pytest.fail(
        "`make -n test` ne montre plus une commande `<python> -m pytest` : la cible "
        f"a changé de forme et ce garde ne la lit plus.\n{r.stdout[:400]}"
    )


def test_the_interpreter_make_would_use_can_load_the_conftest():
    """Le test d'EFFET : cet interpréteur collecte-t-il vraiment ?"""
    python = _resolved_python()
    exe = REPO / python if not python.startswith("/") else Path(python)
    if not exe.exists():
        pytest.fail(
            f"`make test` lancerait `{python}`, qui n'existe pas. "
            "Créer l'environnement (`make sync`) ou corriger la résolution de "
            "`PYTHON` dans le Makefile."
        )

    # UN fichier, pas `tests/` : ce qu'on éprouve est le chargement de `conftest.py`
    # et de ses hooks, payé à l'identique. Collecter les 362 fichiers coûtait 48,8 s
    # à ce garde — un garde cher est un garde qu'on finit par sauter.
    r = subprocess.run(
        [str(exe), "-m", "pytest", f"tests/{Path(__file__).name}",
         "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=REPO, capture_output=True, text=True, timeout=600,
    )
    out = r.stdout + r.stderr

    assert "INTERNALERROR" not in out, (
        f"`make test` lancerait `{python}`, et cet interpréteur sort en "
        "INTERNALERROR avant d'exécuter le moindre test — la suite paraît lancée "
        "et ne prouve rien.\n"
        + "\n".join(line for line in out.splitlines() if "Error" in line)[:400]
    )
    assert "PluginValidationError" not in out, (
        f"`{python}` ne connaît pas un hook déclaré par `tests/conftest.py` "
        "(typiquement `pytest_configure_node`, fourni par `pytest-xdist`). "
        "Installer la dépendance dans CET environnement, ou faire pointer `PYTHON` "
        "sur celui qui la porte."
    )
    assert r.returncode in (0, 5), (
        f"`{python} -m pytest --collect-only` sort {r.returncode} ; attendu 0 "
        f"(des tests collectés) ou 5 (aucun ne correspond au filtre).\n{out[-500:]}"
    )


def test_the_extraction_reads_a_real_make_line():
    """Non-vacuité : si l'extraction ne trouve rien, le garde ci-dessus ne teste rien.

    `_resolved_python` appelle `pytest.fail` quand il ne trouve pas la ligne — mais
    seulement à l'exécution. On épingle ici que le motif reconnaît bien les deux
    formes que le Makefile a portées, et qu'il REFUSE une ligne sans pytest.
    """
    pat = re.compile(r"(\S*python\S*)\s+-m\s+pytest")

    assert pat.search(".venv/bin/python -m pytest tests/ -q -n auto").group(1) == \
        ".venv/bin/python"
    assert pat.search("venv/Scripts/python.exe -m pytest tests/ -q").group(1) == \
        "venv/Scripts/python.exe"
    assert pat.search("docker compose up -d") is None, (
        "le motif attrape une ligne qui ne lance pas pytest"
    )
