"""Un lecteur de total rend l'ABSENCE quand il échoue, jamais un nombre.

Type: Test
Uses: ast, unittest.mock
Depends on: src/dashboard/utils/kpi_helpers.py
Persists in: nothing

Trouvé le 2026-09-17 en balayant les frères de `une-erreur-avalée-devient-une-absence`,
par une recherche à l'AST : **46** `except` du dépôt rendent une valeur vide sans un
mot, **14** d'entre eux enjambent une lecture de données, et **4** enjambent un TOTAL
de locataire — `get_total_streams_s4a`, `get_total_plays_soundcloud`,
`get_total_plays_apple`, `get_soundcloud_likes`. Chacun rendait `0`.

Un zéro est une MESURE — « cet artiste a zéro écoute ». Une lecture qui échoue n'a
rien mesuré. La règle du dépôt le dit déjà (`.claude/rules/python.md`) : « Une lecture
qui échoue ne se déguise pas en "rien à lire". »

⚠️ **La conséquence était bornée en aval, et le dire change la sévérité.** Les deux
surfaces qui lisent ces totaux font `_fmt_big(x) if x else "—"`, donc aucun faux
chiffre n'atteignait l'artiste. Ce qui changeait, c'est qu'un échec de base était
INDISCERNABLE d'un catalogue vide, sans trace, et figé 600 s par `@st.cache_data`.

Mutation record — 2026-09-17, trois mutations :
  1. `return None` → `return 0` dans un des quatre  → **ROUGE** (2 échecs).
  2. le `logger.warning` retiré                      → **ROUGE** (1 échec).
  3. `_READERS` vidé                                 → **VERTE**, et c'était un trou
     dans CE garde : les trois tests paramétrés ne collectent plus rien et la boucle
     du test de comportement itère sur le vide. Fermé par
     `test_the_reader_list_is_not_empty`, écrit après l'avoir vu passer.

---
rex: []
---
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_MODULE = _ROOT / "src" / "dashboard" / "utils" / "kpi_helpers.py"

# Les lecteurs qui rendent UN TOTAL de locataire. Un total est la grandeur pour
# laquelle zéro et « je ne sais pas » ne se ressemblent pas du tout.
_READERS = (
    "get_total_streams_s4a",
    "get_total_plays_soundcloud",
    "get_total_plays_apple",
    "get_soundcloud_likes",
)


def _functions() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def test_the_reader_list_is_not_empty() -> None:
    """Anti-vacuité DE LA LISTE, et elle manquait.

    ⚠️ Mesuré le 2026-09-17 : vider `_READERS` laissait ce fichier VERT. Les trois
    tests paramétrés ne collectent alors plus rien, et la boucle du test de
    comportement itère sur le vide. Un garde dont on peut retirer le sujet sans le
    faire rougir est un garde qu'on retirera.
    """
    assert len(_READERS) >= 4, (
        f"`_READERS` ne porte que {len(_READERS)} nom(s) — les quatre lecteurs de "
        "total mesurés le 2026-09-17 ne sortent pas de cette liste sans raison écrite")


def test_the_named_readers_still_exist() -> None:
    """Et chaque nom désigne une fonction réelle : un renommage rendrait ce garde muet."""
    manquants = [n for n in _READERS if n not in _functions()]
    assert not manquants, (
        f"lecteurs introuvables dans kpi_helpers.py : {manquants}. S'ils ont été "
        "renommés, suivre le nom ; s'ils ont disparu, retirer la ligne ici DANS LE "
        "MÊME COMMIT, sinon ce test garde un fantôme.")


@pytest.mark.parametrize("name", _READERS)
def test_a_failed_read_returns_absence_not_zero(name: str) -> None:
    """Dans le `except`, aucun `return` d'un nombre : l'absence est `None`."""
    fn = _functions()[name]
    fautifs = []
    for handler in [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]:
        for node in ast.walk(handler):
            if not isinstance(node, ast.Return) or node.value is None:
                continue
            rendu = ast.unparse(node.value).strip()
            if rendu != "None":
                fautifs.append(f"ligne {node.lineno} → `{rendu}`")
    assert not fautifs, (
        f"`{name}` fabrique une valeur quand la lecture échoue : {fautifs}.\n"
        "Un zéro est une MESURE ; une lecture qui a échoué n'a rien mesuré. "
        "Rendre `None` — les surfaces affichent déjà « — » dessus.")


@pytest.mark.parametrize("name", _READERS)
def test_a_failed_read_leaves_a_trace(name: str) -> None:
    """Et il le DIT : sans trace, l'échec est indiscernable d'un catalogue vide."""
    fn = _functions()[name]
    muets = []
    for handler in [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]:
        corps = ast.unparse(handler)
        if not any(w in corps for w in ("logger.", "raise", "st.error", "st.warning")):
            muets.append(f"ligne {handler.lineno}")
    assert not muets, (
        f"`{name}` avale l'erreur sans un mot : {muets}. Le cache de 600 s fige "
        "ensuite ce silence, donc l'échec ne laisse aucune trace nulle part.")


def test_the_reader_really_returns_none_when_the_db_raises() -> None:
    """Le COMPORTEMENT, pas seulement la forme : on fait lever la base."""
    from src.dashboard.utils import kpi_helpers

    db = MagicMock()
    db.fetch_query.side_effect = RuntimeError("db down")
    for name in _READERS:
        fn = getattr(kpi_helpers, name)
        brut = getattr(fn, "__wrapped__", fn)      # sous `@st.cache_data`
        assert brut(db, 12) is None, (
            f"`{name}` ne rend pas `None` quand la base lève — il rend "
            f"{brut(db, 12)!r}")
