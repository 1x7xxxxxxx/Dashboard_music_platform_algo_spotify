"""La fenêtre s'applique APRÈS le `LAG`, jamais dans la même portée.

Type: Test
Uses: re
Depends on: src/**/*.py (tout littéral SQL)
Persists in: nothing

Un compteur cumulé devient une quantité quotidienne par `x - LAG(x)`. Le premier
enregistrement d'une partition n'a pas de veille, donc son `LAG` vaut `NULL` — c'est
normal et c'est même juste, tant que la partition commence là où la SÉRIE commence.

Écrire la fenêtre dans le même `WHERE` que le `LAG` borne la PARTITION : le premier
jour de la fenêtre perd sa veille alors qu'elle existe, une ligne en amont, et sa
quantité tombe. Le lecteur voit moins que ce que le compteur a gagné, sans message.

Mesuré le 2026-09-17 sur `utils/pdf_exporter/_collectors.py::_collect_apple_daily`,
base de développement, artiste 1, fenêtre 2025-12-05 → 2025-12-11 : le PDF totalisait
**0** écoute Apple là où **9** ont été gagnées — 100 % de la fenêtre. Les nombres sont
petits (cette base ne porte que 22 relevés Apple) ; le RATIO est le fait, et il vaut
pour toute fenêtre courte.

⚠️ La même règle était DÉJÀ appliquée dans `views/apple_music.py`, qui calcule son
`LAG` dans une CTE sur tout l'historique et borne au SELECT extérieur. Le moteur PDF
ne l'avait pas : une règle appliquée à un seul de ses deux lecteurs. C'est la forme
exacte de `canonical_song_sql`, que ce dépôt a déjà payée, et c'est pourquoi ce garde
lit TOUS les littéraux SQL de `src/` et non un fichier nommé.

Ce qu'il ne couvre PAS
----------------------
Un bornage appliqué en PANDAS après un `LAG` SQL non borné : là, la partition est
correcte et le masque ne retire que des lignes déjà calculées. Et les fenêtres
glissantes autres que `LAG` (`FIRST_VALUE`, `SUM() OVER`) : même cause possible, autre
écriture — trou déclaré.

Mutation record — 2026-09-17 : en remettant `AND date BETWEEN %s AND %s` dans le
`WHERE` qui porte le `LAG` de `_collect_apple_daily`, ce garde le nomme ; avec la CTE,
il passe.

---
rex: []
---
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"

_LAG = re.compile(r"\bLAG\s*\(", re.I)
# Un bornage de fenêtre : `BETWEEN %s AND %s`, `>= %s`, `date >= CURRENT_DATE`…
_WINDOW = re.compile(r"\bBETWEEN\s+%s\s+AND\s+%s|"
                     r"\b(date|day|jour|collected_at|ts)\s*>=?\s*%s|"
                     r"CURRENT_DATE\s*-", re.I)


def _sql_literals() -> list[tuple[str, int, str]]:
    """(fichier, ligne, texte) de chaque chaîne contenant du SQL avec un `LAG`."""
    out = []
    for path in sorted(_SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):            # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if not _LAG.search(node.value):
                continue
            out.append((str(path.relative_to(_ROOT)).replace("\\", "/"),
                        node.lineno, node.value))
        # Les f-strings composées : on recolle leurs morceaux littéraux.
        for node in ast.walk(tree):
            if not isinstance(node, ast.JoinedStr):
                continue
            texte = "".join(v.value for v in node.values
                            if isinstance(v, ast.Constant) and isinstance(v.value, str))
            if _LAG.search(texte):
                out.append((str(path.relative_to(_ROOT)).replace("\\", "/"),
                            node.lineno, texte))
    return out


def test_the_scan_finds_the_lag_queries() -> None:
    """Anti-vacuité : sans requête à lire, tout ce fichier est vert sur rien."""
    found = _sql_literals()
    assert len(found) >= 3, (
        f"seulement {len(found)} littéral(aux) SQL portant un `LAG(` trouvé(s) dans "
        "`src/` — il y en avait 6 le 2026-09-17. Le lecteur AST est cassé, ou les "
        "requêtes ont changé de forme ; dans les deux cas le test d'à côté ne garde "
        "plus rien.")


def test_no_window_bounds_the_partition_it_differences() -> None:
    fautifs = []
    for rel, lineno, sql in _sql_literals():
        # La CTE est la forme correcte : le `LAG` y vit, la fenêtre au SELECT
        # extérieur. On les sépare sur le mot-clé, pas sur une heuristique de
        # présence : dans une requête à CTE, la fenêtre est HORS de la portée du LAG.
        haut = re.split(r"\)\s*SELECT", sql, maxsplit=1, flags=re.I)
        portee_du_lag = haut[0] if len(haut) > 1 else sql
        if not _LAG.search(portee_du_lag):
            continue
        if _WINDOW.search(portee_du_lag):
            fautifs.append(f"{rel}:{lineno}")
    assert not fautifs, (
        f"{len(fautifs)} requête(s) bornent la PARTITION qu'elles différencient.\n"
        "Le premier jour de la fenêtre perd sa veille — qui existe pourtant, une "
        "ligne en amont — et sa quantité tombe sans message. Mesuré le 2026-09-17 : "
        "0 écoute Apple affichée dans un PDF là où 9 ont été gagnées.\n"
        "Remède : calculer le `LAG` dans une CTE sur toute la série, borner au SELECT "
        "extérieur (`views/apple_music.py:155` est la forme de référence).\n  "
        + "\n  ".join(fautifs))
