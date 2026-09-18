#!/usr/bin/env python3
"""Harnais de mutation : un garde qui n'a jamais été vu ROUGE ne garde rien.

Type: Utility (dev)
Uses: ast, subprocess
Triggers: rien — lancé à la main
Persists in: rien (restaure toujours l'arbre)

Pourquoi ce fichier existe — mesuré le 2026-09-18
--------------------------------------------------
Le catalogue portait **230 classes dont la signature n'avait jamais été vue sortir
≠ 0**. Muter à la main coûte deux à trois minutes par classe ; 193 gardes distincts
demandent une journée. Ce harnais propose une mutation, l'applique, lance le garde,
et RESTAURE toujours — quel que soit le résultat, y compris sur exception.

⚠️ Il ne date rien tout seul. Il rend « ce garde a rougi sur telle mutation », et
c'est un humain qui décide si la mutation INCARNE le défaut de la classe. Une
mutation qui casse autre chose ne prouve rien : ce dépôt a mesuré six fois la même
erreur le 2026-09-18 — « muter la première occurrence » touchait un COMMENTAIRE, et
le garde restait vert pendant que je croyais l'avoir mis en défaut.

C'est pourquoi les cibles sont choisies **à l'AST** : seuls les identifiants et les
chaînes qui existent en tant que NŒUDS sont mutés. Une docstring, un commentaire ou
un bloc REX n'a pas de nœud `Name` — il ne peut pas être choisi.
"""
from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
VENV = ROOT / ".venv" / "bin" / "python"


def guard_targets(guard: pathlib.Path) -> list[str]:
    """Les identifiants et chaînes que le garde CITE — ses cibles plausibles."""
    try:
        tree = ast.parse(guard.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return []
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            v = n.value.strip()
            # un identifiant plausible, pas une phrase
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{3,60}", v) and " " not in v:
                out.add(v)
    return sorted(out)


def sources_read(guard: pathlib.Path) -> list[pathlib.Path]:
    """Les fichiers du dépôt que ce garde lit ou importe.

    ⚠️ Trois formes, et la deuxième est celle qui manquait : un chemin littéral, une
    COMPOSITION `ROOT / "src" / "x.py"` — que ce dépôt utilise partout — et un import
    de module. Sans la composition, le harnais rendait « aucune source » sur des gardes
    qui en lisent trois, et concluait « aucune mutation » au lieu de « je n'ai pas
    trouvé où muter ». Les deux se ressemblent dans une sortie et pas du tout dans un
    verdict.
    """
    text = guard.read_text(encoding="utf-8")
    paths: set[pathlib.Path] = set()
    for m in re.finditer(r"['\"]((?:src|airflow|tools|migrations)/[\w/.-]+\.\w+)['\"]", text):
        paths.add(ROOT / m.group(1))
    # `_ROOT / "src" / "dashboard" / "app.py"` — la composition par `/`
    for m in re.finditer(r'(?:\/\s*"[\w.-]+"\s*){2,}', text):
        bits = re.findall(r'"([\w.-]+)"', m.group(0))
        if bits and bits[-1].endswith(".py"):
            paths.add(ROOT.joinpath(*bits))
    for m in re.finditer(r"from\s+((?:src|tools)[\w.]*)\s+import", text):
        p = ROOT / (m.group(1).replace(".", "/") + ".py")
        if p.exists():
            paths.add(p)
        elif (d := ROOT / m.group(1).replace(".", "/")).is_dir():
            paths.update(x for x in d.glob("*.py") if x.name != "__init__.py")
    return sorted(p for p in paths if p.exists() and p.suffix == ".py")


def ast_sites(source: pathlib.Path, needle: str) -> list[tuple[int, int]]:
    """(ligne, colonne) des NŒUDS — jamais un commentaire, jamais une docstring."""
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return []
    docs = set()
    for f in ast.walk(tree):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            continue
        body = getattr(f, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            docs.add(id(body[0].value))
    out = []
    for n in ast.walk(tree):
        if id(n) in docs:
            continue
        if isinstance(n, ast.Name) and n.id == needle:
            out.append((n.lineno, n.col_offset))
        elif isinstance(n, ast.Attribute) and n.attr == needle:
            out.append((n.lineno, n.col_offset))
        elif isinstance(n, ast.Constant) and n.value == needle:
            out.append((n.lineno, n.col_offset))
    return out


def run_guard(guard: pathlib.Path) -> int:
    r = subprocess.run([str(VENV), "-m", "pytest", str(guard.relative_to(ROOT)),
                        "-q", "--no-header", "-x", "--tb=no"],
                       capture_output=True, text=True, cwd=ROOT, timeout=300)
    return r.returncode


def try_mutations(guard: pathlib.Path, budget: int = 6) -> dict:
    """Rend le premier couple (source, cible) qui fait ROUGIR le garde.

    ⚠️ La sauvegarde et la restauration se font en OCTETS. Mesuré le 2026-09-18 : un
    round-trip `read_text`/`write_text` NORMALISE les fins de ligne, et ce harnais a
    réécrit 249 lignes de `csv_exporter.py` (un fichier en CRLF) en croyant le
    restaurer. Une restauration qui ne restaure pas est la classe
    `a-surgical-restore-erases-work-nothing-will-give-back` commise par l'outil.
    """
    if run_guard(guard) != 0:
        return {"skipped": "le garde n'est pas vert avant mutation"}
    cibles = guard_targets(guard)
    essais = 0
    for source in sources_read(guard):
        brut = source.read_bytes()           # l'ORIGINAL, octet pour octet
        original = brut.decode("utf-8")
        lignes = original.splitlines(keepends=True)
        for needle in cibles:
            sites = ast_sites(source, needle)
            if not sites:
                continue
            if essais >= budget:
                return {"epuise": essais}
            essais += 1
            ln, col = sites[0]
            muted = list(lignes)
            muted[ln - 1] = (lignes[ln - 1][:col]
                             + lignes[ln - 1][col:].replace(needle, needle + "_MUTE", 1))
            try:
                source.write_bytes("".join(muted).encode("utf-8"))
                rc = run_guard(guard)
            finally:
                source.write_bytes(brut)      # les OCTETS d'origine, pas un ré-encodage
            if rc != 0:
                return {"source": str(source.relative_to(ROOT)), "cible": needle,
                        "ligne": ln, "essais": essais}
    return {"aucune": essais}


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: mutate_guards.py <tests/test_x.py> [...]"); return 2
    for rel in argv:
        g = ROOT / rel
        if not g.exists():
            print(f"{rel}: introuvable"); continue
        print(f"{rel}: {try_mutations(g)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
