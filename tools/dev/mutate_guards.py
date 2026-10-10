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
import os
import pathlib
import re
import subprocess
import sys
import textwrap

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / ".claude" / "scripts"))
from judgement import is_judgement_pytest  # noqa: E402 — R495, one reading for every tool
from src.utils.env_files import load_project_env  # noqa: E402

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


_IMPORT_ROOTS = ("src", "tools")


def _under_roots(dotted: str) -> bool:
    return dotted.split(".", 1)[0] in _IMPORT_ROOTS


def _module_file(dotted: str) -> pathlib.Path | None:
    """`src.a.b` → `src/a/b.py`, ou `src/a/b/__init__.py` pour un paquet."""
    base = ROOT / dotted.replace(".", "/")
    for cand in (base.with_name(base.name + ".py"), base / "__init__.py"):
        if cand.is_file():
            return cand
    return None


def _docstring_ids(tree: ast.AST) -> set[int]:
    out: set[int] = set()
    for f in ast.walk(tree):
        if not isinstance(f, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = f.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            out.add(id(body[0].value))
    return out


def _script_trees(script: str) -> list[ast.AST]:
    """Les imports d'un script écrit dans une chaîne (AppTest, subprocess).

    ⚠️ Un parse du texte entier échoue sur une indentation (bloc triple-quoté dans une
    fonction), un gabarit `{}` ou un fragment. Rejeter la chaîne entière reproduirait
    exactement le défaut corrigé — une source perdue. D'où : dedent, puis repli ligne à
    ligne sur les seules lignes `import`/`from`, parenthèses de continuation jointes.
    """
    try:
        return [ast.parse(textwrap.dedent(script))]
    except SyntaxError:
        pass
    trees: list[ast.AST] = []
    lines = script.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line.startswith(("import ", "from ")):
            continue
        if "(" in line and ")" not in line:
            while i < len(lines) and ")" not in line:
                line += " " + lines[i].strip()
                i += 1
        try:
            trees.append(ast.parse(line))
        except SyntaxError:
            continue
    return trees


def _imported_sources(tree: ast.AST, depth: int = 0) -> set[pathlib.Path]:
    """Les fichiers `src/`/`tools/` que ces nœuds importent — au NOM importé.

    Ne couvre pas : l'import relatif, `importlib.import_module("src.x")`, `__import__`, ni
    un module dont le nom est un gabarit (`views.{view}`).
    """
    out: set[pathlib.Path] = set()
    docs = _docstring_ids(tree)
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module and _under_roots(n.module):
            pkg = ROOT / n.module.replace(".", "/")
            mod = pkg.with_name(pkg.name + ".py")
            if mod.is_file():
                out.add(mod)
            for alias in n.names:
                # ordre explicite : module `.py`, puis sous-paquet, puis le paquet lui-même
                # (un symbole ré-exporté par son `__init__`)
                if alias.name != "*" and (sub := pkg / f"{alias.name}.py").is_file():
                    out.add(sub)
                elif alias.name != "*" and (sub := pkg / alias.name / "__init__.py").is_file():
                    out.add(sub)
                elif not mod.is_file() and (init := pkg / "__init__.py").is_file():
                    out.add(init)
        elif isinstance(n, ast.Import):
            for alias in n.names:
                if _under_roots(alias.name) and (f := _module_file(alias.name)):
                    out.add(f)
        elif (depth < 2 and isinstance(n, ast.Constant) and isinstance(n.value, str)
              and id(n) not in docs and "import" in n.value):
            for sub_tree in _script_trees(n.value):
                out |= _imported_sources(sub_tree, depth + 1)
    return out


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
    # ⚠️ R493 : `from src.dashboard.views import soundcloud as sc` importe UN module. Le
    # résoudre au paquet entier rendait les 49 vues, triées : les six mutations d'une nuit
    # tombaient dans account.py, admin.py, billing.py — des fichiers que le garde n'importe
    # pas — et trois gardes sains ont été mailés « personne ne l'a vu mordre ».
    # ⚠️ R494 : les imports se lisent à l'AST, plus par regex sur le texte brut. La regex
    # débordait de sa ligne et avalait l'import suivant (93 fichiers perdaient 108 sources
    # réelles), ignorait `import src.x.y`, comptait les docstrings, et résolvait un
    # sous-paquet à l'`__init__` de son parent. Un garde qui ne parse pas garde ses chemins
    # littéraux ci-dessus : seule l'étape d'import est sautée, rien ne lève.
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        tree = None
    if tree is not None:
        paths.update(_imported_sources(tree))
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
    """Lance UN garde, dans l'environnement que le produit résout.

    ⚠️ `load_project_env()` n'était pas appelé jusqu'au 2026-09-18, et
    `tests/test_operator_tools_read_the_apps_env.py` l'a signalé à la minute où ce
    fichier est entré dans une règle de `CLAUDE.md` — donc dans le périmètre de ce
    garde. Il avait raison, et l'enjeu n'est pas théorique : **~40 mutations ont été
    jouées cette nuit-là**. Un garde lancé depuis un shell nu lit un environnement
    différent de celui de la suite ; son verdict peut alors décrire une configuration
    que personne n'exécute, et un « vert » se lire comme « le garde ne mord pas »
    alors qu'il n'a simplement pas pu s'exécuter comme il le fait en vrai.

    C'est très exactement le mode d'échec que ce harnais existe pour attraper, retourné
    contre lui : un outil qui rend un verdict PLAUSIBLE au lieu d'un verdict juste.
    """
    return run_guard_output(guard)[0]


def run_guard_output(guard: pathlib.Path) -> tuple[int, str]:
    """(code de sortie, sortie) — la sortie dit si un rouge est un JUGEMENT ou un plantage."""
    load_project_env()
    r = subprocess.run([str(VENV), "-m", "pytest", str(guard.relative_to(ROOT)),
                        "-q", "--no-header", "-x", "--tb=short"],
                       capture_output=True, text=True, cwd=ROOT, timeout=300,
                       env=os.environ.copy())
    return r.returncode, r.stdout + r.stderr


def is_crash(output: str) -> bool:
    """Le garde est-il TOMBÉ plutôt que d'avoir JUGÉ ? Pur.

    R493 (critic) : renommer `x` en `x_MUTE` fait échouer tout appel — `name 'x_MUTE' is
    not defined`, `KeyError: 'recent'`. Ce rouge prouve que la ligne s'exécute, pas que
    le garde juge ce qu'elle produit ; le dater comme `seen_red` serait un crédit
    silencieux, pire qu'un faux suspect visible. Seul un jugement compte : une assertion
    (`AssertionError`) ou un `pytest.fail` (`Failed:`).

    ⚠️ Lu sur les lignes `E` de `--tb=short`, pas sur un mot n'importe où : un `assert a == b`
    réécrit par pytest s'affiche `E   assert [1000, 400, 100] == [100, 400, 1000]`, SANS le
    mot `AssertionError` — la première version l'aurait classé plantage (mesuré sur le garde
    YouTube, R493). Et un `AssertionError` cité dans un message de log ne juge rien.

    R495 : la lecture vit désormais dans `.claude/scripts/judgement.py`, partagée avec
    `audit_runner`, `arch_benchmark` et la sonde de la gestion d'erreurs — une seule
    définition de « a jugé », au lieu d'une copie par outil.
    """
    return not is_judgement_pytest(output)


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
    essais, tried, crashes = 0, [], []
    for source in sources_read(guard):
        brut = source.read_bytes()           # l'ORIGINAL, octet pour octet
        original = brut.decode("utf-8")
        lignes = original.splitlines(keepends=True)
        for needle in cibles:
            sites = ast_sites(source, needle)
            if not sites:
                continue
            if essais >= budget:
                return {"epuise": essais, "tried": tried, "crashes": crashes}
            essais += 1
            ln, col = sites[0]
            where = f"{source.relative_to(ROOT)}:{ln} `{needle}`"
            tried.append(where)
            muted = list(lignes)
            muted[ln - 1] = (lignes[ln - 1][:col]
                             + lignes[ln - 1][col:].replace(needle, needle + "_MUTE", 1))
            try:
                source.write_bytes("".join(muted).encode("utf-8"))
                rc, out = run_guard_output(guard)
            finally:
                source.write_bytes(brut)      # les OCTETS d'origine, pas un ré-encodage
            if rc != 0 and is_crash(out):
                crashes.append(where)         # atteint, pas jugé : on continue à chercher
            elif rc != 0:
                return {"source": str(source.relative_to(ROOT)), "cible": needle,
                        "ligne": ln, "essais": essais, "tried": tried, "crashes": crashes}
    return {"aucune": essais, "tried": tried, "crashes": crashes}


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
