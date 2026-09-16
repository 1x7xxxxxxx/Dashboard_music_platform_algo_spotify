"""Aucun fichier versionné n'enchaîne un `git commit` derrière un `||`.

Type: Utility
Uses: pathlib
Triggers: pytest
Persists in: nothing

Error class `a-fallback-that-runs-when-the-first-branch-succeeded`.

`||` ne branche pas sur « ai-je obtenu ce que je voulais », il branche sur le **code de
sortie**. Une commande qui réussit *mal* n'active jamais le repli, et une qui échoue
l'active alors qu'on ne l'attendait pas. Mesuré le 2026-09-16, deux fois, en sens
opposés :

  * `git commit … || git commit -m "…"` — le premier a ÉCHOUÉ, donc le repli a remplacé
    le message par un autre, en silence ;
  * `git commit -C ORIG_HEAD 2>/dev/null || git commit -F -` — le premier a RÉUSSI, et a
    copié le message et la date d'auteur d'un vieux commit de fusion. Le contenu livré
    était juste ; son message annonçait une autre brique. Le `2>/dev/null` a en plus
    supprimé la seule trace de ce qui s'était passé.

Un commit a **un seul résultat acceptable** : celui-là, avec ce message-là. Un geste de
ce genre ne se replie pas — s'il échoue, on lit l'échec.

## Portée, et pourquoi elle est étroite

Les deux instances étaient des commandes tapées à la main, que rien ne peut lire après
coup. Ce garde ne les attrape donc pas et ne le prétend pas. Il tient la seule surface
lisible : les fichiers VERSIONNÉS. C'est là que la forme deviendrait durable — un
`Makefile` ou un script qui la porte la rejoue à chaque exécution, pour tout le monde.

Chercher tous les `||` du dépôt rendrait des dizaines de cas parfaitement légitimes
(`test -f x || exit 1`), et un compteur bruyant fait ignorer les vrais. La question est
donc resserrée sur le geste qui a coûté : **un commit en position de repli**.

Mutation record — 2026-09-16, vue rouge : `|| git commit -m "retry"` ajouté à une
recette du `Makefile` → rouge en nommant fichier et ligne ; retiré, vert. Seconde
mutation, celle qui compte : la même ligne écrite en COMMENTAIRE (`# … || git commit …`)
→ reste VERT, parce qu'un garde qui rougit sur la prose qui le documente est le premier
qu'on désactive — quatre pris ainsi en une soirée dans ce dépôt. Troisième mutation :
`subprocess.run("git push || git commit -F -")` ajouté dans un `.py` de `tools/` → rouge,
donc la lecture par AST des `.py` n'a pas troqué la portée contre la propreté.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Les surfaces versionnées où une commande shell est REJOUÉE : recettes, scripts, CI.
_SURFACES = (
    ("Makefile",),
    ("tools", "**/*.sh"),
    ("tools", "**/*.py"),
    (".claude", "**/*.sh"),
    (".github", "**/*.yml"),
    ("deploy", "**/*.sh"),
)

# `… || git commit …` ou `… || <quoi que ce soit> commit -m`, sur une ligne de CODE.
#
# ⚠️ La première version écrivait `\bcommit\b`, et elle a dénoncé `Makefile:546` :
#     pip install --user pre-commit >/dev/null || pip install pre-commit;
# `\b` traite le tiret comme une frontière de mot, donc **`pre-commit` contient
# `commit`**. Le garde aurait fait renommer une ligne parfaitement saine — et c'est la
# façon dont un garde perd sa crédibilité : un faux positif coûte plus cher qu'un trou,
# parce qu'il apprend que son rouge est du bruit.
# Les classes voisines exigent donc `git commit` ou `commit -m`, et une frontière qui
# compte le tiret comme un caractère de mot.
_FALLBACK_COMMIT = re.compile(
    r"\|\|\s*[^|#\n]*?(?:(?<![\w-])git\s+commit(?![\w-])"
    r"|(?<![\w-])commit\s+-[mCF](?![\w-]))")


def _candidate_files() -> list[Path]:
    out: list[Path] = []
    for surface in _SURFACES:
        if len(surface) == 1:
            path = REPO / surface[0]
            if path.is_file():
                out.append(path)
            continue
        root, pattern = surface
        base = REPO / root
        if base.is_dir():
            out.extend(p for p in base.glob(pattern)
                       if p.is_file() and "__pycache__" not in str(p))
    return sorted(set(out))


def _strip_comment(line: str) -> str:
    """Ce qui reste d'une ligne une fois son commentaire retiré.

    Sans ça, écrire SUR le défaut le déclenche — y compris dans le fichier qui
    l'explique. Ce dépôt appelle ça `a-bash-hook-that-blocks-the-prose-about-the-gesture`
    et l'a payé trois commandes bloquées d'affilée le 2026-09-12.
    """
    stripped = line.lstrip()
    if stripped.startswith(("#", "//", "--")):
        return ""
    # Un `#` au milieu d'une ligne de shell ou de Makefile ouvre un commentaire dès lors
    # qu'il est précédé d'un espace ; `$#` ou une URL avec ancre ne comptent pas.
    return re.split(r"\s#", line, maxsplit=1)[0]


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Les `id()` des chaînes qui sont des DOCSTRINGS — de la prose, pas des commandes."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                out.add(id(first.value))
    return out


def _offenders() -> list[str]:
    bad = []
    for path in _candidate_files():
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.suffix == ".py":
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            docs = _docstring_nodes(tree)
            bad.extend(
                f"{path.relative_to(REPO)}:{node.lineno}"
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docs and _FALLBACK_COMMIT.search(node.value))
            continue
        for number, line in enumerate(source.splitlines(), 1):
            if _FALLBACK_COMMIT.search(_strip_comment(line)):
                bad.append(f"{path.relative_to(REPO)}:{number}")
    return bad


def test_the_scan_sees_files_at_all() -> None:
    """Non-vacuité : une liste de motifs qui ne trouve aucun fichier est muette."""
    files = _candidate_files()
    assert len(files) >= 20, (
        f"seulement {len(files)} fichier(s) balayé(s) — les motifs de `_SURFACES` ne "
        "correspondent plus à l'arborescence, et ce garde ne regarde rien")
    assert any(p.name == "Makefile" for p in files), "le Makefile n'est plus balayé"


def test_the_predicate_would_see_the_shape_that_cost() -> None:
    """Le prédicat rougit sur la forme réelle, et se tait sur sa propre prose."""
    assert _FALLBACK_COMMIT.search('\tgit commit -q -F - || git commit -m "retry"')
    assert _FALLBACK_COMMIT.search("\tgit commit -C ORIG_HEAD || git commit -F -")
    assert not _FALLBACK_COMMIT.search(_strip_comment(
        '\techo ok  # jamais `a || git commit -m "x"` : voir la classe'))
    assert not _FALLBACK_COMMIT.search(_strip_comment(
        '# git push || git commit -m "x"'))
    # Le faux positif qui a fait resserrer le motif, gardé comme cas négatif.
    assert not _FALLBACK_COMMIT.search(
        "\tpip install --user pre-commit >/dev/null || pip install pre-commit;"), (
        "`pre-commit` contient `commit` — le motif redénonce une ligne saine")


def test_no_versioned_file_puts_a_commit_in_a_fallback() -> None:
    offenders = _offenders()
    assert not offenders, (
        "un `git commit` est en position de repli derrière un `||` :\n  "
        + "\n  ".join(offenders)
        + "\n\n`||` branche sur le CODE DE SORTIE, pas sur « ai-je obtenu ce que je "
          "voulais ». Le 2026-09-16, les deux sens ont coûté : un repli qui s'active "
          "sur un échec remplace le message ; un premier terme qui réussit MAL "
          "empêche le repli de servir. Un commit a un seul résultat acceptable — "
          "écris-le en une commande, et lis l'échec s'il échoue.")
