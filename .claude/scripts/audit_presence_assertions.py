#!/usr/bin/env python3
"""Une assertion de PRÉSENCE peut être satisfaite par un COMMENTAIRE du fichier visé.

Type: Utility (audit)
Uses: ast, pathlib
Triggers: rien — appelé par la signature de la classe `guard-satisfied-by-its-own-comment`
Persists in: rien

Le défaut, mesuré le 2026-09-18
--------------------------------
`assert "MATERIALIZED" in sql` lisait `migrations/119_gold_s4a_release_cohort.sql`. Le
mot vit DEUX fois dans ce fichier : une fois dans la CTE (`WITH linked AS MATERIALIZED`)
et une fois dans le commentaire qui explique pourquoi elle l'est. Le défaut a été remis
en place en entier — la CTE inlinée — et **les 16 tests du fichier sont restés verts**.

C'est `guard-matches-its-own-comment` retourné : là-bas le garde ROUGIT sur sa prose et
on s'en aperçoit tout de suite ; ici il reste VERT grâce à elle, et rien ne le signale.
C'est la même cause — une lecture textuelle qui ne distingue pas le code de la prose —
avec la conséquence qui ne se voit pas.

Ce que ce script rend, et ce qu'il ne rend pas
-----------------------------------------------
Il rend les assertions `"<littéral>" in <variable>` où la variable porte du TEXTE BRUT
de fichier. Il ne peut pas décider si le littéral vit réellement dans un commentaire du
fichier visé : la variable est résolue à l'exécution, pas à la lecture. C'est donc une
liste de CANDIDATS à relire, `kind: heuristic`, pas un verdict.

Une assertion sur une liste, un dict ou un ensemble (`in names`, `in called`, `in keys`)
est structurelle : elle n'est pas concernée et n'est pas comptée.

---
rex:
  - date: 2026-09-18
    issue: "Le balayage n a ete ecrit qu APRES qu une mutation eut montre un garde vert sur le defaut entier ; une assertion de presence sur du texte brut etait invisible parce qu elle ressemble a un garde."
    fix: "Balayage AST des assertions de presence sur du texte brut, restreint aux litteraux citables en prose (>= 6 caracteres, sans ponctuation de code). 110 sites rendus."
    severity: warn
---
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"

# Les noms de variable qui, dans ce dépôt, portent du texte brut lu d'un fichier.
RAW_NAMES = {
    "src", "body", "text", "sql", "conftest", "dag", "doc", "code", "SRC", "DAG",
    "recipe", "branch", "joined", "tool", "auth", "alerts", "mk", "caddy",
    "dockerfile", "ui", "head", "logic", "block", "active_txt", "archive_txt",
    "auth_src", "lsrc", "onboarding", "assets", "resume", "window", "ts_body",
    "premium_block", "net", "expr", "tpl", "statement", "query", "cohorte", "reach",
}
# Un littéral qui contient de la ponctuation de code ne peut pas passer pour de la
# prose française ou anglaise ; on ne le compte pas.
CODEISH = re.compile(r"""[=(){}\[\]<>;%"']""")


def sites() -> list[tuple[str, int, str, str]]:
    out: list[tuple[str, int, str, str]] = []
    for path in sorted(TESTS.glob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assert):
                continue
            test = node.test
            if not (isinstance(test, ast.Compare) and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.In)
                    and isinstance(test.left, ast.Constant)
                    and isinstance(test.left.value, str)
                    and isinstance(test.comparators[0], ast.Name)):
                continue
            if test.comparators[0].id not in RAW_NAMES:
                continue
            literal = test.left.value
            if len(literal) < 6 or CODEISH.search(literal):
                continue
            out.append((path.name, node.lineno, literal, test.comparators[0].id))
    return out


def main() -> int:
    found = sites()
    print(f"{len(found)} assertion(s) de présence sur du texte brut, "
          "littéral citable en commentaire")
    for name, lineno, literal, var in found:
        print(f"  {name}:{lineno}  {literal!r} in {var}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
