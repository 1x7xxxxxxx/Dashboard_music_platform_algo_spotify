"""Le CODE d'un fichier, sa prose retirée — pour qu'un garde ne se lise pas lui-même.

Type: Utility
Uses: ast, tokenize
Triggers: importé par les gardes qui affirment la présence d'un identifiant
Persists in: rien

Pourquoi ce module existe — mesuré le 2026-09-18
-------------------------------------------------
`assert "<mot>" in fichier.read_text()` ne distingue pas le code de la prose du
fichier visé. Dix assertions du dépôt étaient dans ce cas, et deux d'entre elles
étaient **déjà vertes à vide** : le mot ne vivait plus que dans un commentaire.

Trois défauts entiers ont été remis en place sans faire rougir leur garde :

* `pd.to_datetime(values, utc=True)` → `pd.to_datetime(values)` — `utils/tz.py`
  nomme `utc=True` quatre fois dans ses docstrings (classe P1
  `timestamptz-parsed-across-a-dst-change`, six tests verts) ;
* `PostgresHandler.from_env_or_config()` → un DSN bâti à la main — le fichier
  nomme la méthode deux fois de plus en prose (cinq tests verts) ;
* `WITH linked AS MATERIALIZED (` → `WITH linked AS (` — le mot vivait dans le
  commentaire qui explique pourquoi la CTE est matérialisée (seize tests verts).

C'est `guard-matches-its-own-comment` retourné : là-bas le garde rougit sur sa
prose et on le corrige dans l'heure ; ici il VERDIT grâce à elle et rien ne le
dit. Classe `guard-satisfied-by-its-own-comment`.

La règle qui en sort : une assertion de présence lit `code_of(chemin)`, jamais
`chemin.read_text()`. Quand c'est la PRÉSENCE D'UN COMMENTAIRE qui est le sujet —
il en existe une, délibérée — on lit le texte entier et on dit pourquoi.

Contrôle : `python3 .claude/scripts/audit_presence_assertions.py --proven`.
"""
from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path


def code_of(path: str | Path) -> str:
    """Le texte de `path` privé de ses commentaires et de ses docstrings.

    Marche sur du Python (tokenize + AST), et sur tout fichier de ligne à ligne —
    shell, SQL, YAML, Dockerfile — en retirant les lignes qui commencent par `#`,
    `--` ou `//`. Un commentaire de FIN de ligne y survit : c'est assumé, et c'est
    pourquoi la présence d'un identifiant se cherche sur un motif assez précis pour
    ne pas se confondre avec une phrase.
    """
    p = Path(path)
    texte = p.read_text(encoding="utf-8", errors="replace")
    # ⚠️ LE MARKDOWN N'A PAS DE COMMENTAIRE DE LIGNE — mesuré le 2026-09-18, quelques
    # heures après la livraison de ce module. `#` y est un TITRE, et `--` une ligne de
    # séparation de tableau. Les retirer faisait lire un document comme s'il était vide
    # de ses en-têtes, donc toute assertion portant sur un titre était déclarée
    # « satisfaite par la prose ». Un faux positif d'un outil anti-faux-positif.
    if p.suffix in (".md", ".markdown", ".rst", ".txt"):
        return texte
    if p.suffix != ".py":
        return "\n".join(x for x in texte.splitlines()
                          if not x.lstrip().startswith(("#", "--", "//")))
    lignes = texte.splitlines(keepends=True)
    debuts = [0]
    for ligne in lignes:
        debuts.append(debuts[-1] + len(ligne))

    def offset(ligne: int, colonne: int) -> int:
        return debuts[ligne - 1] + colonne

    # ON EFFACE SUR PLACE, on ne reconstruit pas.
    #
    # La première version joignait les jetons par des sauts de ligne : `from src.utils
    # import x` devenait `from\nsrc\n.\nutils…`, donc TOUTE assertion portant une
    # phrase de plusieurs mots cessait de matcher. Trois gardes sont passés au rouge
    # sur du code parfaitement correct — un faux positif est aussi coûteux qu'un
    # faux négatif, et c'est ce qui l'a montré tout de suite.
    caracteres = list(texte)

    def effacer(deb: int, fin: int) -> None:
        for i in range(deb, min(fin, len(caracteres))):
            if caracteres[i] != "\n":
                caracteres[i] = " "

    try:
        for tok in tokenize.generate_tokens(io.StringIO(texte).readline):
            if tok.type == tokenize.COMMENT:
                effacer(offset(*tok.start), offset(*tok.end))
    except (tokenize.TokenError, IndentationError):
        return texte
    try:
        arbre = ast.parse(texte)
    except SyntaxError:
        return "".join(caracteres)
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.Module, ast.FunctionDef,
                                  ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if not (noeud.body and isinstance(noeud.body[0], ast.Expr)
                and isinstance(noeud.body[0].value, ast.Constant)
                and isinstance(noeud.body[0].value.value, str)):
            continue
        litteral = noeud.body[0].value
        effacer(offset(litteral.lineno, litteral.col_offset),
                offset(litteral.end_lineno, litteral.end_col_offset))
    return "".join(caracteres)
