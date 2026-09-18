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
import io
import pathlib
import re
import sys
import tokenize

ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"

# Les noms de variable qui, dans ce dépôt, portent du texte brut lu d'un fichier.
RAW_NAMES = {
    "src", "body", "text", "sql", "conftest", "dag", "doc", "code", "SRC", "DAG",
    "recipe", "branch", "joined", "tool", "auth", "alerts", "mk", "caddy",
    "dockerfile", "ui", "head", "logic", "block", "active_txt", "archive_txt",
    "auth_src", "lsrc", "onboarding", "assets", "resume", "window", "ts_body",
    "premium_block", "net", "expr", "tpl", "statement", "query", "cohorte", "reach",
    "tz", "backup", "monitor", "app", "app_src", "door",
}
# Un littéral qui contient de la ponctuation de code ne peut pas passer pour de la
# prose française ou anglaise ; on ne le compte pas dans la liste de CANDIDATS.
CODEISH = re.compile(r"""[=(){}\[\]<>;%"']""")

# Ces assertions épinglent DÉLIBÉRÉMENT la présence d'un commentaire — c'est leur
# objet, pas un défaut. Chacune doit dire pourquoi.
EXEMPTES = {
    # Elle existe pour que personne ne « simplifie » le garde AST en grep : le
    # commentaire nommant la variable d'environnement retirée EST le sujet.
    ("test_identity_has_no_env_fallback.py",
     "test_the_exact_comment_that_would_break_a_grep_is_present"),
    # Le sujet EST la note qui explique pourquoi un détecteur a été retiré : sans
    # elle, le suivant le ré-ajoute et la décision devient un cycle. L'assertion
    # voisine du même test, elle, lit bien le CODE.
    ("test_no_detector_is_written_and_never_called.py",
     "test_the_deleted_detector_stays_deleted"),
}


def prose_and_code(path: pathlib.Path) -> tuple[str, str]:
    """(prose, code) d'un fichier — commentaires et docstrings d'un côté."""
    txt = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix != ".py":
        lignes = txt.splitlines()
        prose = "\n".join(x for x in lignes if x.lstrip().startswith(("#", "--", "//")))
        code = "\n".join(x for x in lignes if not x.lstrip().startswith(("#", "--", "//")))
        return prose, code
    prose_parts, code_parts = [], []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(txt).readline):
            (prose_parts if tok.type == tokenize.COMMENT else code_parts).append(tok.string)
    except (tokenize.TokenError, IndentationError):
        return txt, txt
    try:
        tree = ast.parse(txt)
    except SyntaxError:
        return "\n".join(prose_parts), "\n".join(code_parts)
    code = "\n".join(code_parts)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                prose_parts.append(doc)
                code = code.replace(doc, "")
    return "\n".join(prose_parts), code


def resolve(node: ast.AST, env: dict) -> "pathlib.Path | None":
    """Évalue un chemin composé de `/`, de noms connus et de littéraux."""
    if isinstance(node, ast.Name):
        value = env.get(node.id)
        return pathlib.Path(value) if value is not None else None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if len(node.value) > 120 or "\n" in node.value:
            return None
        return pathlib.Path(node.value)
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Path" and node.args:
        return resolve(node.args[0], env)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left, right = resolve(node.left, env), resolve(node.right, env)
        if left is None or right is None or right.is_absolute():
            return None
        try:
            return left / right
        except (ValueError, OSError):
            return None
    return None


def _presence_asserts(tree: ast.AST) -> list[tuple[int, str, str]]:
    """(ligne, littéral, variable) de chaque `assert "<lit>" in <nom>`."""
    out = []
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
        out.append((node.lineno, test.left.value, test.comparators[0].id))
    return out


def sites() -> list[tuple[str, int, str, str]]:
    """Les CANDIDATS : une présence sur du texte brut, littéral citable en prose."""
    out: list[tuple[str, int, str, str]] = []
    for path in sorted(TESTS.glob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for lineno, literal, var in _presence_asserts(tree):
            if var not in RAW_NAMES or len(literal) < 6 or CODEISH.search(literal):
                continue
            out.append((path.name, lineno, literal, var))
    return out


def _enclosing_test(tree: ast.AST, lineno: int) -> str:
    best = "?"
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
                and node.lineno <= lineno <= (node.end_lineno or node.lineno)):
            best = node.name
    return best


def proven() -> list[tuple[str, int, str, str, bool]]:
    """Les sites PROUVÉS : le littéral vit aussi dans la prose du fichier visé.

    C'est la moitié que le balayage de candidats ne peut pas rendre : on résout le
    fichier réellement lu, on sépare sa prose de son code, et on regarde si
    l'assertion tiendrait encore une fois le code retiré.
    """
    out = []
    for path in sorted(TESTS.glob("test_*.py")):
        texte = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(texte)
        except (SyntaxError, UnicodeDecodeError):
            continue
        env: dict = {"ROOT": ROOT, "_ROOT": ROOT, "REPO": ROOT, "_REPO": ROOT,
                     "SRC": ROOT / "src", "_SRC": ROOT / "src",
                     "TESTS": TESTS, "_TESTS": TESTS}
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)):
                got = resolve(node.value, env)
                if got is not None and (got.is_dir() or got.is_file()):
                    env[node.targets[0].id] = got
        # LES LIAISONS SONT PAR FONCTION, jamais par fichier.
        #
        # Mesuré le 2026-09-18 : liées au fichier, `src = A.read_text()` d'un test et
        # `src = B.read_text()` d'un autre se recouvraient, et le balayage nommait un
        # fichier que l'assertion ne lit pas. Un audit qui désigne la mauvaise cible
        # coûte le temps qu'on passe à la vérifier — deux faux positifs sur dix.
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            lus: dict[str, pathlib.Path] = {}
            for node in ast.walk(fn):
                if (isinstance(node, ast.Assign) and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and isinstance(node.value, ast.Call)
                        and getattr(node.value.func, "attr", "") == "read_text"):
                    got = resolve(node.value.func.value, env)
                    if got is not None and got.is_file():
                        lus[node.targets[0].id] = got
            for lineno, literal, var in _presence_asserts(fn):
                if var not in lus or len(literal) < 4:
                    continue
                if (path.name, _enclosing_test(tree, lineno)) in EXEMPTES:
                    continue
                prose, code = prose_and_code(lus[var])
                if literal in prose:
                    out.append((path.name, lineno, literal,
                                lus[var].relative_to(ROOT).as_posix(), literal in code))
    return out


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--candidates"
    if mode == "--proven":
        found = proven()
        print(f"{len(found)} assertion(s) PROUVÉE(S) satisfiables par la prose du "
              "fichier visé")
        for name, lineno, literal, target, in_code in found:
            etat = ("code+prose — verte dès que le code part"
                    if in_code else "PROSE SEULE — déjà verte à vide")
            print(f"  {name}:{lineno}  {literal!r} -> {target}\n     {etat}")
        return 1 if found else 0
    found = sites()
    print(f"{len(found)} assertion(s) de présence sur du texte brut, "
          "littéral citable en commentaire")
    for name, lineno, literal, var in found:
        print(f"  {name}:{lineno}  {literal!r} in {var}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
