#!/usr/bin/env python3
"""Rend la liste des tests affectés par les fichiers modifiés — ou la suite entière.

Pourquoi cet outil existe
-------------------------
`ARCHITECTURE.md` §10bis **refuse** de différer les tests en fin de boucle et
prescrit de **restreindre le périmètre** (ARCH p154-155). C'était de la doctrine
sans outil : rien, dans les huit dépôts, ne sélectionnait les tests affectés par
un diff. Une doctrine sans outil est exactement ce que R18 appelle mesurer
l'artefact au lieu de l'effet.

Le seul mode de défaillance qui compte
--------------------------------------
**Un sélecteur qui rate un test affecté est PIRE que pas de sélecteur** : il rend
un vert qui ne veut rien dire, et il le rend vite, ce qui le rend crédible. Tout
ce fichier est écrit autour de ce constat.

La règle de conception est donc : **en cas de doute, tout renvoyer.** Sept
situations forcent la suite entière, et chacune est là parce qu'elle rend le
graphe d'imports non concluant, pas parce qu'elle est rare :

1. le dépôt n'est pas un dépôt git, ou le diff est illisible ;
2. un fichier modifié n'est **pas** du `.py` — ce peut être une fixture, un
   `.json` de configuration, un `.sql`, une donnée de test ;
3. un `conftest.py` a bougé — il s'applique à tout un sous-arbre sans qu'aucun
   `import` ne le nomme ;
4. un fichier de configuration de la suite a bougé (`pyproject.toml`,
   `pytest.ini`, `setup.cfg`, `tox.ini`) ;
5. un fichier du dépôt ne se parse pas — le graphe est alors incomplet et on ne
   sait pas de combien ;
6. un fichier modifié ne se résout en aucun module connu — on ne peut pas
   remonter ses importateurs ;
7. aucun test n'a été trouvé — un sélecteur qui rend « rien » sur un dépôt qui a
   des tests est indistinguable d'un sélecteur cassé.

S'y ajoute une règle qui ne force PAS la suite entière mais élargit la sélection :
un test qui fait un import dynamique (`importlib`, `__import__`) est **toujours**
inclus, parce que rien de statique ne dira ce qu'il charge.

Ce que l'outil ne sait pas faire
--------------------------------
Il ne voit que les imports **statiques**. Un test qui atteint le code modifié par
un plugin pytest tiers, une injection de dépendance à l'exécution, un
`subprocess` ou un fichier de données n'est pas détecté — sauf si la règle 2
l'attrape par la bande. C'est la raison pour laquelle `--dry` existe : comparer
la sélection au comptage complet avant de faire confiance à l'outil sur un dépôt
donné.

    python3 select_tests.py                    # depuis le dépôt courant
    python3 select_tests.py --base origin/main # contre une autre référence
    python3 select_tests.py --dry              # explique, ne rend pas la liste
    python3 select_tests.py --self-test        # R3 — vu rouge avant d'être cru
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

# Artefacts regenerables : ni sources, ni fixtures, ni donnees. Les ignorer est
# sans risque pour le seul mode de defaillance qui compte — rater un test
# affecte — puisqu'aucun test n'est atteignable DEPUIS un artefact.
_ARTEFACTS = ("__pycache__/", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/",
              ".tox/", "htmlcov/", ".coverage", "node_modules/")


def _EST_ARTEFACT(chemin: str) -> bool:
    c = chemin.replace("\\", "/")
    return (c.endswith((".pyc", ".pyo")) or ".egg-info/" in c
            or any(a in c for a in _ARTEFACTS))


SUITE_CONFIG = {"pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"}
DYNAMIC = {"importlib", "__import__"}


def _git(root: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def changed_files(root: Path, base: str | None) -> list[str] | None:
    """Fichiers modifiés, ou None si on ne peut pas savoir (→ suite entière)."""
    if _git(root, "rev-parse", "--git-dir") is None:
        return None
    args = ["diff", "--name-only", base] if base else ["diff", "--name-only", "HEAD"]
    out = _git(root, *args)
    if out is None:
        return None
    files = set(out.split())
    # Les fichiers non suivis comptent : un test tout neuf est affecté par
    # définition, et un module tout neuf peut déjà être importé.
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    if untracked:
        files |= set(untracked.split())
    return sorted(files)


def is_test(rel: str) -> bool:
    name = Path(rel).name
    return name.startswith("test_") or name.endswith("_test.py")


def source_roots(root: Path) -> list[Path]:
    """Les racines depuis lesquelles Python importe — pas seulement la racine git.

    Pourquoi. `module_name` calculait le nom pointé relativement à la racine du
    dépôt : `src/app/repo.py` devenait `src.app.repo`, quand les tests écrivent
    `from app import repo`, donc `app.repo`. Les deux ne se rencontraient jamais,
    et le sélecteur répondait « 0 test atteint le module modifié » — pas « je ne
    sais pas conclure », mais une conclusion FAUSSE, qui fait sauter exactement
    les tests qui attrapent la régression.

    Mesuré le 2026-07-30 : msdr et streamlytics sont en `src/`, trading_bot en
    `python/`. Le sélecteur est déployé sur les trois et aveugle sur les trois.
    Il n'a rien cassé pour une seule raison — R34 : personne ne l'appelle.

    Une racine de sources est un dossier qui CONTIENT un paquet, c'est-à-dire un
    sous-dossier avec `__init__.py`. Le critère est structurel, pas une liste de
    noms devinés : `src`, `python`, `lib` ou n'importe quoi d'autre passent.
    """
    roots = [root]
    try:
        children = [d for d in root.iterdir() if d.is_dir() and d.name not in PRUNE]
    except OSError:
        return roots
    for child in sorted(children):
        try:
            if any((sub / "__init__.py").is_file()
                   for sub in child.iterdir() if sub.is_dir()):
                roots.append(child)
        except OSError:
            continue
    return roots


def module_name(root: Path, path: Path, roots: list[Path] | None = None) -> str:
    """Nom pointé d'un fichier, `__init__` replié sur son paquet.

    Le nom est calculé depuis la racine de sources la PLUS PROFONDE qui contient
    le fichier : `src/app/repo.py` sous la racine `src/` donne `app.repo`, et
    c'est ce que le test écrit.
    """
    base = root
    for r in (roots or [root]):
        try:
            path.relative_to(r)
        except ValueError:
            continue
        if len(r.parts) > len(base.parts):
            base = r
    rel = path.relative_to(base).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


PRUNE = {".git", ".venv", "venv", "env", "node_modules", "__pycache__",
         "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache",
         "site-packages", ".tox", "htmlcov", ".idea", ".vscode"}


def _walk_python(root: Path) -> list[Path]:
    """Les `.py` du dépôt, en ÉLAGUANT pendant la descente.

    La première version faisait `root.rglob("*.py")` puis filtrait sur
    `p.parts` — donc elle traversait `.venv` en entier avant de le jeter.
    Mesuré sur `trading_bot` (403 modules, sur `/mnt/c`) : **61 s**. C'est F6
    mot pour mot — « un parcours non élagué coûte plus que tout le reste » — et
    F4 explique pourquoi ça fait si mal ici : un `stat` coûte 511× plus cher sur
    `/mnt/c` que sur un disque natif. Un outil censé faire GAGNER du temps avant
    de lancer les tests ne peut pas en coûter une minute.
    """
    import os
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PRUNE and not d.startswith(".")]
        for f in filenames:
            if f.endswith(".py"):
                out.append(Path(dirpath) / f)
    return out


def build_graph(root: Path) -> tuple[dict[str, set[str]], set[str], list[str]]:
    """(module -> modules importés), tests dynamiques, fichiers non parsables."""
    py = _walk_python(root)
    roots = source_roots(root)
    known = {module_name(root, p, roots): p for p in py}
    imports: dict[str, set[str]] = {}
    dynamic: set[str] = set()
    unparsable: list[str] = []

    for p in py:
        mod = module_name(root, p, roots)
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError, OSError):
            unparsable.append(str(p.relative_to(root)))
            continue
        got: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    got.add(a.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relatif : résoudre contre le paquet du fichier
                    pkg = mod.split(".")[:-node.level] if node.level <= mod.count(".") + 1 else []
                    prefix = ".".join(pkg + ([node.module] if node.module else []))
                else:
                    prefix = node.module or ""
                got.add(prefix)
                for a in node.names:
                    got.add(f"{prefix}.{a.name}" if prefix else a.name)
            elif isinstance(node, ast.Name) and node.id == "__import__":
                dynamic.add(mod)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id == "importlib":
                dynamic.add(mod)
        if "importlib" in got:
            dynamic.add(mod)

        # On ne garde que ce qui existe DANS le dépôt ; le reste est une
        # dépendance tierce, dont on ne suit pas les modifications ici.
        resolved = set()
        for name in got:
            if name in known:
                resolved.add(name)
            else:
                # `from a.b import c` où c est un symbole : a.b est le module.
                head = name.rsplit(".", 1)[0]
                if head in known:
                    resolved.add(head)
        imports[mod] = resolved

    return imports, dynamic, unparsable


def importers_closure(imports: dict[str, set[str]], seeds: set[str]) -> set[str]:
    """Tous les modules qui atteignent `seeds`, transitivement.

    La transitivité est le coeur du sujet : si le test importe A, que A importe
    B et que B a changé, le test est affecté. Un sélecteur qui s'arrête au
    premier saut rate ce cas — et c'est précisément la mutation que
    `--self-test` exerce.
    """
    reverse: dict[str, set[str]] = {}
    for mod, deps in imports.items():
        for d in deps:
            reverse.setdefault(d, set()).add(mod)
    seen = set(seeds)
    stack = list(seeds)
    while stack:
        cur = stack.pop()
        for up in reverse.get(cur, ()):
            if up not in seen:
                seen.add(up)
                stack.append(up)
    return seen


def select(root: Path, base: str | None = None, _max_depth: int | None = None) -> dict:
    """Rend {'all': bool, 'tests': [...], 'reason': str}.

    `_max_depth` n'existe que pour `--self-test` : il bride la fermeture
    transitive afin de prouver que la brider fait bien rater un test. Voir R3.
    """
    changed = changed_files(root, base)
    if changed is None:
        return {"all": True, "tests": [], "reason": "pas un dépôt git, ou diff illisible"}
    if not changed:
        return {"all": False, "tests": [], "reason": "aucun fichier modifié"}

    # Les ARTEFACTS de compilation ne sont pas des sources. Un `.pyc` sous
    # `__pycache__/` qui bouge declenchait la regle « fichier non-Python
    # modifie » et rendait la suite entiere — mesure du 2026-08-03 sur
    # plugin_vst, ou un .pyc suivi par git neutralisait le selecteur en
    # permanence. Les ecarter n'affaiblit rien : un artefact regenerable ne peut
    # pas etre une fixture, une config ou une donnee de test.
    changed = [c for c in changed if not _EST_ARTEFACT(c)]
    if not changed:
        return {"all": False, "tests": [],
                "reason": "seuls des artefacts de compilation ont change"}

    for c in changed:
        n = Path(c).name
        if n in SUITE_CONFIG:
            return {"all": True, "tests": [], "reason": f"configuration de suite modifiée ({n})"}
        if n == "conftest.py":
            return {"all": True, "tests": [],
                    "reason": "conftest.py modifié — il s'applique sans être importé"}
        if not c.endswith(".py"):
            return {"all": True, "tests": [],
                    "reason": f"fichier non-Python modifié ({c}) — fixture, config ou donnée possible"}

    imports, dynamic, unparsable = build_graph(root)
    if unparsable:
        return {"all": True, "tests": [],
                "reason": f"{len(unparsable)} fichier(s) non parsable(s) — graphe incomplet : "
                          f"{', '.join(unparsable[:3])}"}

    all_tests = sorted(m for m in imports if is_test(m.replace(".", "/") + ".py"))
    if not all_tests:
        return {"all": True, "tests": [],
                "reason": "aucun test trouvé — un sélecteur qui rend « rien » n'est pas distinguable d'un sélecteur cassé"}

    seeds = set()
    for c in changed:
        mod = module_name(root, root / c, source_roots(root))
        if mod in imports:
            seeds.add(mod)
        else:
            return {"all": True, "tests": [],
                    "reason": f"{c} ne se résout en aucun module connu — importateurs introuvables"}

    if _max_depth is None:
        reached = importers_closure(imports, seeds)
    else:  # chemin de mutation, --self-test uniquement
        reached, frontier = set(seeds), set(seeds)
        reverse: dict[str, set[str]] = {}
        for mod, deps in imports.items():
            for d in deps:
                reverse.setdefault(d, set()).add(mod)
        for _ in range(_max_depth):
            frontier = {u for f in frontier for u in reverse.get(f, ())} - reached
            reached |= frontier

    picked = {t for t in all_tests if t in reached}
    picked |= {t for t in all_tests if t in dynamic}   # import dynamique : toujours
    picked |= {t for t in all_tests if t in seeds}     # le test lui-même a changé

    return {"all": False, "tests": sorted(picked),
            "reason": f"{len(picked)}/{len(all_tests)} tests atteignent {len(seeds)} module(s) modifié(s)"}


def as_paths(tests: list[str]) -> list[str]:
    return [t.replace(".", "/") + ".py" for t in tests]


# ---------------------------------------------------------------- R3

def self_test() -> int:
    """Vu ROUGE sur une sélection bridée, VERT sur la sélection complète.

    Un sélecteur qu'on n'a jamais vu rater ce qu'il doit attraper est un test de
    présence déguisé (REX R3). On construit donc une chaîne à DEUX sauts —
    test → intermédiaire → feuille — et on vérifie deux choses :
      * la fermeture transitive complète attrape le test ;
      * une fermeture bridée à un saut le RATE.
    Si la seconde assertion échoue, c'est que la première ne prouvait rien.
    """
    import shutil
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="select-tests-selftest-"))
    ok = True
    try:
        (root / "pkg").mkdir()
        (root / "tests").mkdir()
        (root / "pkg" / "__init__.py").write_text("")
        (root / "pkg" / "leaf.py").write_text("VALUE = 1\n")
        (root / "pkg" / "middle.py").write_text("from pkg.leaf import VALUE\n")
        (root / "tests" / "test_far.py").write_text("from pkg.middle import VALUE\ndef test_x(): assert VALUE\n")
        (root / "tests" / "test_unrelated.py").write_text("def test_y(): assert True\n")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "base"], check=True)

        (root / "pkg" / "leaf.py").write_text("VALUE = 2\n")

        # Le layout `src/` — le defaut du 2026-07-30, garde ici pour qu'il ne
        # revienne pas. `src/app/repo.py` doit se nommer `app.repo`, pas
        # `src.app.repo`, sinon `from app import repo` ne le rejoint jamais et le
        # selecteur rend « 0 test atteint » : une conclusion FAUSSE, qui fait
        # sauter les tests qui attrapent la regression. msdr et streamlytics
        # sont en `src/`, trading_bot en `python/`.
        src_root = Path(tempfile.mkdtemp(prefix="select-tests-srclayout-"))
        (src_root / "src" / "app").mkdir(parents=True)
        (src_root / "tests").mkdir()
        (src_root / "src" / "app" / "__init__.py").write_text("")
        (src_root / "src" / "app" / "repo.py").write_text("N = 1\n")
        (src_root / "tests" / "test_repo.py").write_text(
            "from app import repo\ndef test_n(): assert repo.N\n")
        (src_root / "tests" / "test_other.py").write_text("def test_z(): assert True\n")
        subprocess.run(["git", "init", "-q", str(src_root)], check=True)
        subprocess.run(["git", "-C", str(src_root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(src_root), "-c", "user.email=t@t",
                        "-c", "user.name=t", "commit", "-qm", "base"], check=True)
        (src_root / "src" / "app" / "repo.py").write_text("N = 2\n")
        srcsel = select(src_root)
        cas_src = [
            ("VERT   layout `src/` : le test qui importe `app.repo` est atteint",
             not srcsel["all"] and "tests.test_repo" in srcsel["tests"]),
            ("VERT   ... et le test sans rapport ne l'est pas",
             "tests.test_other" not in srcsel["tests"]),
        ]
        shutil.rmtree(src_root, ignore_errors=True)

        full = select(root)
        crippled = select(root, _max_depth=1)

        cases = list(cas_src) + [
            ("VERT   la fermeture complète attrape le test à 2 sauts",
             "tests.test_far" in full["tests"]),
            ("VERT   elle n'attrape PAS le test sans rapport",
             "tests.test_unrelated" not in full["tests"]),
            ("ROUGE  bridée à 1 saut, elle RATE le test à 2 sauts",
             "tests.test_far" not in crippled["tests"]),
        ]

        # Les sept sorties « tout renvoyer » doivent réellement se déclencher.
        (root / "data.json").write_text("{}")
        cases.append(("VERT   un fichier non-Python force la suite entière", select(root)["all"]))
        (root / "data.json").unlink()

        (root / "conftest.py").write_text("")
        cases.append(("VERT   un conftest.py force la suite entière", select(root)["all"]))
        (root / "conftest.py").unlink()

        (root / "pkg" / "broken.py").write_text("def (:\n")
        cases.append(("VERT   un fichier non parsable force la suite entière", select(root)["all"]))
        (root / "pkg" / "broken.py").unlink()

        # Le quasi-raté. Un `.py` DANS un répertoire élagué — `.claude/hooks/`
        # est le cas réel — n'entre pas dans le graphe. Il ne doit donc PAS
        # sortir « 0 test » : la règle 6 (« ne se résout en aucun module
        # connu ») doit le rattraper et forcer la suite entière.
        # Garder `.claude` dans le graphe serait PIRE, pas mieux : ses modules
        # portent des noms inimportables (`.claude.hooks.x`), donc aucun import
        # ne les atteint, donc la fermeture rendrait l'ensemble vide — un raté
        # silencieux au lieu d'un repli sûr.
        (root / ".claude" / "hooks").mkdir(parents=True)
        (root / ".claude" / "hooks" / "observe.py").write_text("X = 1\n")
        r_hook = select(root)
        cases.append(("VERT   un .py dans un répertoire élagué force la suite entière",
                      r_hook["all"]))
        shutil.rmtree(root / ".claude")

        for label, passed in cases:
            print(f"  {'OK ' if passed else 'KO '} {label}")
            ok &= passed
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    print("Un sélecteur qui rate un test affecté rend un vert qui ne veut rien dire."
          if ok else "ÉCHEC — ne pas livrer.")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--base", help="référence git (défaut : HEAD)")
    ap.add_argument("--dry", action="store_true", help="expliquer, ne pas rendre la liste")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    r = select(args.root.resolve(), args.base)
    if args.dry:
        verdict = "SUITE ENTIÈRE" if r["all"] else f"{len(r['tests'])} test(s)"
        print(f"{verdict} — {r['reason']}")
        for t in as_paths(r["tests"]):
            print(f"  {t}")
        return 0
    if r["all"]:
        print("tests/", file=sys.stdout)
    else:
        for t in as_paths(r["tests"]):
            print(t)
    print(f"# {r['reason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
