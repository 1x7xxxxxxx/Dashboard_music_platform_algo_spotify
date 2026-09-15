"""La porte de la base ne tire pas un framework d'interface.

Type: Test
Uses: pytest, ast, subprocess
Depends on: src/dashboard/utils/__init__.py
Persists in: nothing

Ce qui a été mesuré (2026-09-15)
--------------------------------
`src/dashboard/utils/__init__.py` est la porte que **50 fichiers de tests**, l'API
(`src/api/deps.py`) et tout script de base franchissent pour obtenir une connexion
Postgres. Elle portait `import streamlit as st` en ligne 1, à cause d'une seule
chose : un `@st.cache_data` sur `logo_html` — et un décorateur s'évalue À L'IMPORT.

Le coût, inscrit dans `tests/db_gate.py:60-71` : **5,30 s** pour cette porte contre
**0,19 s** pour `src.database.postgres_handler` seul. Payé une fois par processus
pytest, donc par worker xdist, et à la COLLECTE.

`requirements-api.txt` le documentait comme une contrainte subie : « streamlit is
here on purpose … removing it means untangling that dependency first — a separate
change, with its own risk ». C'est ce changement-là.

Ce que ce garde demande, en DEUX temps
--------------------------------------
* la STRUCTURE — aucun `import streamlit` au niveau module, lu par `ast` (un
  `import` dans un corps de fonction est légitime et n'est pas attrapé) ;
* l'EFFET — un interpréteur neuf importe la porte et `streamlit` n'est PAS dans
  `sys.modules`. C'est la moitié qui compte : la première mesure un artefact, la
  seconde mesure ce que l'artefact est censé produire. Ce dépôt a déjà payé pour
  cette distinction — « mesurer un artefact là où la question est un effet ».
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DOOR = _ROOT / "src" / "dashboard" / "utils" / "__init__.py"


def _module_level_imports(path: Path) -> set[str]:
    """Les modules importés au NIVEAU MODULE — pas ceux importés dans une fonction."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in tree.body:                      # `.body` et non `ast.walk` : c'est
        if isinstance(node, ast.Import):        # exactement la différence demandée
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return out


def test_the_door_does_not_import_streamlit_at_module_level() -> None:
    assert "streamlit" not in _module_level_imports(_DOOR), (
        f"{_DOOR.relative_to(_ROOT)} réimporte Streamlit au niveau module.\n"
        "Cette porte coûte alors 5,30 s au lieu de 0,19 s, à chaque processus pytest et "
        "à l'image de l'API. Si une fonction a besoin de `st`, importe-le DANS la "
        "fonction ; si c'est un décorateur, le code appartient à un autre module "
        "(`src/dashboard/utils/branding.py` est le précédent)."
    )


def test_importing_the_door_really_leaves_streamlit_out() -> None:
    """L'EFFET, mesuré dans un interpréteur neuf — pas l'artefact.

    Un test qui ne lirait que l'AST resterait vert si un sous-module importé au
    niveau module tirait Streamlit à son tour. C'est la question posée ici.
    """
    code = (
        "import sys;"
        "import src.dashboard.utils;"
        "sys.exit(1 if 'streamlit' in sys.modules else 0)"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=_ROOT,
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, (
        "importer `src.dashboard.utils` charge Streamlit dans un interpréteur neuf.\n"
        "Le niveau module est peut-être propre, mais une des dépendances importées en "
        "tête le tire quand même — c'est l'effet qui compte, pas la déclaration.\n"
        f"rc={out.returncode}\nstderr:\n{out.stderr[-2000:]}"
    )


def test_the_effect_probe_can_actually_fail() -> None:
    """Non-vacuité : la sonde doit savoir dire NON, sinon elle dit toujours OUI."""
    code = ("import sys;"
            "import streamlit;"
            "sys.exit(1 if 'streamlit' in sys.modules else 0)")
    out = subprocess.run([sys.executable, "-c", code], cwd=_ROOT,
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 1, (
        "la sonde rend 0 alors que Streamlit vient d'être importé explicitement : "
        "elle ne peut pas détecter ce qu'elle prétend détecter."
    )
