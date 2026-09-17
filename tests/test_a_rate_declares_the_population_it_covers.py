"""Un taux publié dit sur quelle population il porte.

Type: Test
Uses: ast
Depends on: tools/dev/error_class_health.py
Persists in: nothing

Le défaut
---------
`error-class-health.md` publiait la strate `by_scope` avec le verdict « **séparent** » :
0,83 récidive/classe-mois quand `ne couvre pas:` est écrit, **0,0** quand il ne l'est pas,
intervalles disjoints. Lu tel quel, ça dit « écrire la portée protège ».

L'autre lecture est **aussi compatible avec les mêmes données**, et rien ne l'écrivait :
une récidive se compte en **lignes d'histoire ajoutées** à une classe. Les classes sans
portée écrite sont, par construction, celles qu'on n'a pas rouvertes — donc celles dont
l'histoire ne bouge pas. Le zéro peut mesurer une protection ou une **inattention**.

Mesuré le 2026-09-17 : la strate porte sur **80 classes de 380**, soit **21 %**. Un taux
publié sur un cinquième du catalogue et lu comme s'il portait sur tout est la forme la
plus discrète de `un-nombre-affirmé-qui-n-a-pas-été-mesuré`.

Pourquoi le garde vise le GÉNÉRATEUR
------------------------------------
`error-class-health.md` est régénéré à chaque `make error-health`. Une phrase ajoutée au
document disparaît au premier `make`. La seule place qui tient est le code qui l'écrit.
"""
from __future__ import annotations

import ast
from pathlib import Path

_GEN = Path(__file__).resolve().parents[1] / "tools" / "dev" / "error_class_health.py"
_DOC = Path(__file__).resolve().parents[1] / ".claude" / "dev-docs" / "error-class-health.md"


def test_the_generator_computes_the_covered_population() -> None:
    """La part doit être CALCULÉE, jamais tapée — sinon elle se périme en silence."""
    # ⚠️ STRUCTURE, pas texte. La première version faisait
    # `'pop["classes"] - h["scope_without_not_covered"]' in src` — une assertion qu'un
    # simple COMMENTAIRE aurait satisfaite. `test_a_guard_reads_structure_not_text`
    # l'a refusée, et à raison : c'est la forme qui a pris trois gardes au vert sur
    # leur propre défaut le 2026-09-04.
    tree = ast.parse(_GEN.read_text(encoding="utf-8"))
    assign = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.Assign) and len(n.targets) == 1
                   and isinstance(n.targets[0], ast.Name)
                   and n.targets[0].id == "scoped"), None)
    assert assign is not None, (
        "`scoped` a disparu du générateur : la part du catalogue couverte par la "
        "strate `by_scope` n'est plus calculée, donc plus déclarée")

    expr = assign.value
    assert isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Sub), (
        "`scoped` n'est plus une SOUSTRACTION : un chiffre tapé à la main se "
        f"périmerait à la première classe écrite (vu {ast.dump(expr)[:80]})")
    keys = {n.value for n in ast.walk(expr)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert {"classes", "scope_without_not_covered"} <= keys, (
        "`scoped` ne se dérive plus de `classes` moins `scope_without_not_covered` — "
        f"les clés lues sont {sorted(keys)}")


def test_the_document_declares_the_population_of_its_rate() -> None:
    """L'EFFET : le document rendu doit porter la déclaration, pas seulement le code."""
    doc = _DOC.read_text(encoding="utf-8")
    assert "% du catalogue" in doc and "by_scope" in doc, (
        "`error-class-health.md` ne déclare plus sur quelle part du catalogue porte la "
        "strate `by_scope`. Le taux redevient citable comme s'il décrivait toutes les "
        "classes — ce qu'il ne fait pas.")
    assert "on ne regarde que là" in doc, (
        "la lecture alternative a disparu du document. Sans elle, « les strates se "
        "séparent » se lit comme une preuve que la portée protège, alors que les mêmes "
        "données admettent « on ne regarde pas là ».")
