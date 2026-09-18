"""Garde : la porte qui refuse un faux balayage tourne là où elle bloque.

Type: Test
Uses: pathlib, re
Triggers: pytest
Persists in: nothing

Pourquoi ce fichier existe
--------------------------
`make error-health` compte les faux balayages **après coup**. Il en a compté **97** le
2026-09-17 : 97 classes dont le champ `siblings:` disait « j'ai relancé le garde, il est
vert » — ce qui prouve que le prédicat de CE garde ne trouve rien, jamais qu'il n'y a
rien. Mesuré trois fois la nuit du 17 au 18, dont **un garde vert sur 8 sites vivants**.

Les 97 ont été balayées (R137, close le 2026-09-18) et ont rendu **310 défauts réels**
dans du code dont personne ne s'était plaint. Mais **un compteur remis à zéro ne dit rien
sur le prochain** : rien n'empêchait d'en écrire un 98ᵉ, et le compteur ne l'aurait
signalé qu'au prochain `make error-health`.

Ce que ce fichier tient — et pourquoi trois assertions, pas une
----------------------------------------------------------------
1. La porte EXISTE (`--sweep-verdict` est un drapeau réel de `audit_runner.py`).
2. Elle est CÂBLÉE dans le workflow qui bloque — le dépôt a mesuré qu'une étape
   annoncée et non câblée « se lit comme une étape qui tourne » (`Makefile:545`).
3. Elle n'est pas VACANTE : elle voit des centaines de balayages, pas zéro.

Le point 3 est là parce que la première écriture de cette porte lisait
`h.get("siblings")` sur des en-têtes qui **n'extraient pas ce champ**. Elle sortait 0 en
annonçant « 0 balayage déclaré » sur un catalogue qui en porte 402 : **verte parce
qu'elle ne voyait rien**. Ni ruff ni la lecture ne pouvaient le dire — seule l'exécution.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = _ROOT / ".claude" / "scripts" / "audit_runner.py"
_CI = _ROOT / ".github" / "workflows" / "ci.yml"


def _flags_declared() -> set[str]:
    """Les drapeaux réellement DÉCLARÉS à argparse, lus dans l'AST.

    ⚠️ Pas `'"--sweep-verdict"' in source`. Cette première écriture a été refusée par
    `test_no_new_textual_guard_is_added` et `test_no_new_assertion_compares_strings_
    against_source_text` le jour même — et ils ont raison : un nom présent quelque part
    dans un fichier ne dit rien de ce que le code en FAIT. Le drapeau pourrait vivre
    dans un commentaire, dans ce docstring, ou dans un message d'erreur, et
    l'assertion resterait verte sur un `audit_runner.py` qui ne l'expose plus.
    """
    arbre = ast.parse(_RUNNER.read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") == "add_argument"
                and n.args
                and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str)):
            out.add(n.args[0].value)
    return out


def test_the_flag_extraction_is_not_vacuous() -> None:
    """Sans extraction, l'assertion suivante est verte pour une raison sans rapport."""
    flags = _flags_declared()
    assert len(flags) > 5, (
        f"seulement {len(flags)} drapeau(x) extrait(s) de `audit_runner.py` — "
        "l'extraction AST a raté sa cible.")
    assert "--lint" in flags, (
        "`--lint`, un drapeau connu de longue date, n'est pas trouvé : l'extraction "
        "ne lit pas ce qu'elle croit lire.")


def test_the_gate_exists_as_a_flag() -> None:
    assert "--sweep-verdict" in _flags_declared(), (
        "`audit_runner.py` ne DÉCLARE plus `--sweep-verdict` à argparse. C'est la seule "
        "chose qui refuse un faux balayage AU MOMENT DE L'ÉCRIRE ; le compteur ne le "
        "voit qu'après.")


def test_the_gate_runs_in_the_workflow_that_blocks() -> None:
    assert _CI.is_file(), "ci.yml absent"
    corps = _CI.read_text(encoding="utf-8")
    assert "audit_runner.py --sweep-verdict" in corps, (
        "`--sweep-verdict` n'est plus lancé par `ci.yml`. Une porte qui n'est câblée "
        "nulle part n'est pas une porte : ce dépôt a mesuré qu'une étape annoncée et "
        "non câblée « se lit comme une étape qui tourne » — et c'est exactement ce qui "
        "avait laissé 97 faux balayages s'écrire.")
    # Les deux autres contrôles câblés le même jour, pour la même raison.
    for outil in ("audit_runner.py --coverage", "audit_unreachable_tools.py"):
        assert outil in corps, (
            f"`{outil}` n'est plus lancé par `ci.yml`. Il y a été ajouté le 2026-09-18 "
            "après mesure : il ne tournait qu'à la main.")


def test_the_gate_is_not_vacuous() -> None:
    """Elle VOIT les balayages — sinon elle est verte sur n'importe quoi.

    C'est la leçon de sa propre première écriture : elle lisait un champ que son parseur
    n'extrait pas, donc elle annonçait « 0 balayage déclaré » et sortait 0 sur un
    catalogue qui en porte 402.
    """
    r = subprocess.run([sys.executable, str(_RUNNER), "--sweep-verdict"],
                       capture_output=True, text=True, cwd=str(_ROOT), timeout=120)
    assert r.returncode == 0, (
        f"la porte refuse le catalogue actuel :\n{r.stdout}\n{r.stderr}")
    m = re.search(r"(\d+)\s+balayage", r.stdout)
    assert m, f"la porte ne dit plus combien de balayages elle voit :\n{r.stdout}"
    vus = int(m.group(1))
    assert vus > 100, (
        f"la porte ne voit que {vus} balayage(s) — le catalogue en porte des centaines. "
        "Elle serait VERTE sur n'importe quoi. C'est le défaut exact de sa première "
        "écriture : elle lisait `h.get(\"siblings\")` sur des en-têtes qui n'extraient "
        "pas ce champ.")
