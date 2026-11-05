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
2. un fichier modifié configure l'ENVIRONNEMENT de toute la suite sans qu'aucun test
   ne le nomme : lock (`uv.lock`), `requirements*`, `.env*`, `*.sql`, `config/` ;
   (jusqu'au 2026-09-25 : TOUT fichier non-`.py`. Ce dépôt modifie un `.md`, un
   `.yml` ou `.test_durations` dans presque chaque séance, et `make test-changed`
   rendait alors la suite entière — 9 656 tests, trois fois sur trois ce jour-là.
   Un autre non-`.py` sélectionne désormais par mention, par DOSSIER et par module
   VOISIN, chacun avec sa cellule rouge au `--self-test`) ;
   ⚠️ `*.sql` reste ici, et le rétrécir a été REFUSÉ le 2026-10-08 (R469) : une
   migration casse par un NOT NULL vu des fixtures, une vue or au-dessus de la table, un
   trigger qu'aucun test ne nomme — pas par la mention de son nom ; et ce que le diff
   change n'atteint la base qu'après `make migrate`, que le sélecteur ne voit pas. La
   version minimale sûre (migration faite SEULEMENT d'`ALTER DATABASE|ROLE … SET`)
   couvrait 0 des 144 migrations ce jour-là — 147 elle-même est un bloc `DO` ;
3. un `conftest.py` a bougé — il s'applique à tout un sous-arbre sans qu'aucun
   `import` ne le nomme ;
4. un fichier de configuration de la suite a bougé (`pyproject.toml`,
   `pytest.ini`, `setup.cfg`, `tox.ini`) ;
5. un fichier du dépôt ne se parse pas — le graphe est alors incomplet et on ne
   sait pas de combien ;
6. un fichier modifié **que Python peut importer** ne se résout en aucun module
   connu — on ne peut pas remonter ses importateurs ;
7. aucun test n'a été trouvé — un sélecteur qui rend « rien » sur un dépôt qui a
   des tests est indistinguable d'un sélecteur cassé.

S'y ajoutent quatre règles qui ne forcent PAS la suite entière mais élargissent
la sélection :

- un test qui fait un import dynamique (`importlib`, `__import__`) est
  **toujours** inclus, parce que rien de statique ne dira ce qu'il charge ;
- un fichier qui **manipule `sys.path`** sans que le sélecteur puisse lire le
  dossier inséré est toujours inclus, pour la même raison : après une insertion de
  chemin, `import x` peut désigner n'importe quoi. Quand le dossier se lit dans la
  source (`ROOT / "tools" / "dev"`, `Path(__file__).parent`) et existe, il est
  parcouru et les imports du fichier se résolvent À TRAVERS lui, fichier par
  fichier (`syspath_inserts`) : le test n'est plus pris que si ce qu'il importe a
  changé (2026-10-20 : 90 tests sur 109 étaient pris à chaque diff) ;
- un test dont la source **nomme en clair** un fichier modifié est inclus, même
  s'il ne l'importe pas : c'est la forme qu'a un test qui lance un script par
  `subprocess` ;
- un `.py` qu'**aucune racine d'imports ne couvre** n'est atteignable par aucun
  `import` : on sélectionne les tests qui le nomment plutôt que de rendre la
  suite entière. Voir `racines_imports()` — c'est ce qui rend le sélecteur
  utilisable dans un dépôt dont tout le Python vit sous `.claude/`.

Ce que l'outil ne sait pas faire
--------------------------------
Il ne voit que les imports **statiques**, plus les deux élargissements ci-dessus.
Un test qui atteint le code modifié par un plugin pytest tiers, une injection de
dépendance à l'exécution ou un fichier de données n'est pas détecté — sauf si la
règle 2 l'attrape par la bande. C'est la raison pour laquelle `--dry` existe :
comparer la sélection au comptage complet avant de faire confiance à l'outil sur
un dépôt donné.

L'élargissement `subprocess` est textuel, donc approximatif : il peut prendre un
test de trop. C'est le sens du compromis — un faux positif coûte un test, un faux
négatif coûte la garantie tout entière.

    python3 select_tests.py                    # depuis le dépôt courant
    python3 select_tests.py --base origin/main # contre une autre référence
    python3 select_tests.py --dry              # explique, ne rend pas la liste
    python3 select_tests.py --self-test        # R3 — vu rouge avant d'être cru

---
rex: []
---
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
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


# Etat ECRIT PAR LE HARNAIS pendant qu'on travaille : telemetrie du curateur,
# journal d'observations, sessions. Ce n'est pas un artefact de compilation — un
# test PEUT le lire — mais ce n'est pas non plus une source, et il bouge a chaque
# requete. Suivi par git, il declenchait la regle 2 (« fichier non-Python
# modifie ») en PERMANENCE : mesure du 2026-08-03 sur n8n, ou un
# `.claude/curator/usage.json` suivi rendait SUITE ENTIERE quoi qu'on touche.
#
# On ne les JETTE pas comme un `.pyc` : on les retire du declencheur « suite
# entiere » tout en les gardant dans la detection par mention litterale. Un test
# qui nomme `usage.json` reste donc selectionne — la garantie tient, seul le
# repli aveugle tombe.
# Nommes un par un, jamais par dossier. La premiere version portait
# `.claude/curator/` en entier : le dry-run sur la flotte a montre qu'elle
# emportait `SCHEDULE.md` et `pinned.txt`, qui sont ecrits A LA MAIN et vivent
# dans le meme dossier que la telemetrie. Un filtre trop large ne se voit pas —
# il retire silencieusement du contenu du declencheur, ce qui est exactement le
# mode de defaillance que ce fichier declare pire que pas de selecteur.
_ETAT_GENERE = (".claude/curator/usage.json", ".claude/sessions/",
                ".claude/observations.jsonl", ".claude/telemetry/")


def _EST_ETAT_GENERE(chemin: str) -> bool:
    c = chemin.replace("\\", "/")
    return any(e in c for e in _ETAT_GENERE)


SUITE_CONFIG = {"pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"}

# Non-Python files that configure the suite or the environment every test runs in:
# nothing names them, yet any test may depend on them. Everything else non-Python is
# selected by mention, by directory and by neighbouring module (rule 2, 2026-09-25).
_ENV_NAMES = {"uv.lock", "Pipfile.lock", "poetry.lock", "init_db.sql"}


def _FORCE_LA_SUITE(chemin: str) -> bool:
    c = chemin.replace("\\", "/")
    n = Path(c).name
    # `.streamlit/` (R338): the runtime reads it on every render, never by a name a test
    # could carry — measured by `make select-audit`, three render tests read it unselected.
    # T649: `requirements*` means pip's files (requirements.txt, requirements-dev.in, requirements/…), never
    # any file so named — docs/architecture/requirements.yaml, a catalogue tests name, forced the whole suite.
    pip_reqs = (n.startswith("requirements") and Path(n).suffix in (".txt", ".in", "")) or c.startswith("requirements/")
    return (n in _ENV_NAMES or pip_reqs or n.startswith(".env")
            or c.endswith(".sql") or c.startswith(("config/", ".streamlit/")))
DYNAMIC = {"importlib", "__import__"}


# Pourquoi `git` a échoué, et pas seulement QU'il a échoué. Mesuré le 2026-09-15 :
# `select_tests.py` annonçait « pas un dépôt git, ou diff illisible » **dans un dépôt
# git parfaitement sain**, pendant qu'un `audit_runner --deterministic` lançait ses
# 296 pytest sur /mnt/c. `git diff --name-only HEAD` y dépassait les 30 s ; le
# `except subprocess.SubprocessError` avalait le `TimeoutExpired` et rendait la même
# valeur qu'un répertoire sans `.git`.
#
# Le VERDICT était juste — suite entière, la direction sûre. C'est la RAISON qui
# mentait, et elle envoie chercher au mauvais endroit : on vérifie son dépôt au lieu
# de regarder la charge. Un diagnostic qui nomme la mauvaise cause coûte plus cher
# qu'un diagnostic absent, parce qu'on le croit.
_DERNIERE_PANNE_GIT: str | None = None


def _git(root: Path, *args: str) -> str | None:
    global _DERNIERE_PANNE_GIT
    try:
        r = subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        _DERNIERE_PANNE_GIT = (
            f"`git {' '.join(args)}` a dépassé 30 s — la machine est chargée, ce "
            "n'est PAS un problème de dépôt. Relancer au calme rendra la liste courte."
        )
        return None
    except (OSError, subprocess.SubprocessError) as e:
        _DERNIERE_PANNE_GIT = f"`git {' '.join(args)}` injoignable : {type(e).__name__}"
        return None
    if r.returncode != 0:
        _DERNIERE_PANNE_GIT = (
            f"`git {' '.join(args)}` sort {r.returncode} : "
            f"{(r.stderr or '').strip()[:120] or 'aucun message'}"
        )
        return None
    return r.stdout


def push_remote(root: Path) -> str | None:
    """The remote a push goes to, in git's order: branch.<b>.pushRemote, remote.pushDefault,
    branch.<b>.remote, the only remote, else `origin`. None: no remote at all.
    Same table as the master's tools/dev/git_upstream.py (this file travels alone to the fleet;
    test_git_upstream.py runs both copies against the same configurations)."""
    global _DERNIERE_PANNE_GIT
    panne = _DERNIERE_PANNE_GIT
    try:   # an unset key (`config --get` rc 1) or a detached HEAD is a state, not a git failure
        remotes = (_git(root, "remote") or "").split()
        if not remotes:
            return None
        branch = (_git(root, "symbolic-ref", "--short", "-q", "HEAD") or "").strip()
        keys = ([f"branch.{branch}.pushRemote"] if branch else []) + ["remote.pushDefault"] + \
            ([f"branch.{branch}.remote"] if branch else [])
        for key in keys:
            v = (_git(root, "config", "--get", key) or "").strip()
            if v in remotes:
                return v
        return remotes[0] if len(remotes) == 1 else "origin"
    finally:
        _DERNIERE_PANNE_GIT = panne


def _unpushed_base(root: Path) -> str | None:
    """Where the unpushed work starts: merge-base with the upstream; without one, the common
    ancestor of what the push remote already holds; no remote at all, HEAD; else None.

    R464 — against `HEAD` alone, `make test-changed` run AFTER a commit saw an empty diff,
    selected nothing, stamped the tree green, and the pre-push gate let an untested commit
    go (2026-10-08: a catalogue commit, CI red). Diffing from the upstream covers the
    working tree AND every commit not yet pushed; it can only widen the selection.

    A branch WITHOUT upstream fell back to that same bare HEAD (measured 2026-10-18: `dev`, no
    upstream, 1 commit ahead → `[]`, the gate let it through). With a remote, the base is the
    boundary of `rev-list HEAD --not --remotes=<remote>`; when it cannot be found, None — the
    whole suite. Never bare HEAD while a remote exists.
    """
    global _DERNIERE_PANNE_GIT
    panne = _DERNIERE_PANNE_GIT
    out = _git(root, "merge-base", "HEAD", "@{upstream}")
    _DERNIERE_PANNE_GIT = panne   # no upstream is a normal state, not a git failure
    if out and out.strip():
        return out.strip()
    remote = push_remote(root)
    if remote is None:
        return "HEAD"   # nothing is ever pushed from here: the working tree is the diff
    out = _git(root, "rev-list", "--boundary", "HEAD", "--not", f"--remotes={remote}")
    if out is None:
        return None
    lines = out.split()
    if not lines:
        return "HEAD"   # HEAD already on the remote: only the working tree is new
    bounds = [ln[1:] for ln in lines if ln.startswith("-")]
    base = bounds[0] if len(bounds) == 1 else (
        (_git(root, "merge-base", "--octopus", *bounds) or "").strip() if bounds else "")
    if not base:
        _DERNIERE_PANNE_GIT = (f"pas d'amont, et aucune base commune avec le remote `{remote}` : "
                               "les commits non poussés ne se lisent pas")
        return None
    return base


def changed_files(root: Path, base: str | None) -> list[str] | None:
    """Fichiers modifiés, ou None si on ne peut pas savoir (→ suite entière)."""
    if _git(root, "rev-parse", "--git-dir") is None:
        return None
    base = base or _unpushed_base(root)
    if base is None:
        return None
    args = ["diff", "--name-only", base]
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
    # R305 — `archive/` holds tests of retired hooks; under `.claude/.retired/` the dot hid
    # them from pytest, in `archive/` a move selected them and they failed to import.
    if rel.startswith("archive/"):
        return False
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

    S'y ajoutent les racines que le dépôt DÉCLARE — voir `racines_declarees()`.
    """
    roots = [root]
    try:
        children = [d for d in root.iterdir() if d.is_dir() and d.name not in PRUNE]
    except OSError:
        children = []
    for child in sorted(children):
        try:
            if any((sub / "__init__.py").is_file()
                   for sub in child.iterdir() if sub.is_dir()):
                roots.append(child)
        except OSError:
            continue
    for d in racines_declarees(root):
        if d not in roots:
            roots.append(d)
    return roots


# R447 — an import written INSIDE a string a test executes elsewhere (`AppTest.from_string`,
# `python -c`): `from src.dashboard.views.{view} import show` has no AST edge, and the test
# was red in CI on 2026-10-05 for a view change the selector did not select it for. A name
# followed by `.{` (or by the end of an f-string piece) is a TEMPLATE: every module under
# it is a dependency. Prose that happens to say « from the … » resolves to nothing.
_IMPORT_IN_STRING = re.compile(
    r"\b(?P<kw>from|import)\s+(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)"
    r"(?P<tpl>\.(?:\{|$))?"
    r"(?:\s+import\s+(?:\((?P<paren>[^)]*)\)|(?P<names>[\w, ]+)))?", re.MULTILINE)


def _imported_names(group: str) -> list[str]:
    """`b as c, d` or a parenthesised `(b,  # note\n c)` → ['b', 'd'] / ['b', 'c'].

    R494 — the `as` alias was kept in the name (`pkg.views.soundcloud as sc`), which
    resolves to nothing and fell back to the PACKAGE. The first token of each element is
    the imported name; prose (`errors are shown`) still yields a name nothing resolves.
    """
    group = re.sub(r"#[^\n]*", "", group)
    return [n.split()[0] for n in group.split(",") if n.split()]


def imports_in_strings(tree: ast.AST) -> tuple[set[str], set[str]]:
    """(module names, templated package prefixes) imported from string literals. Pure."""
    names: set[str] = set()
    prefixes: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and "import" in node.value):
            continue
        for m in _IMPORT_IN_STRING.finditer(node.value):
            if m["tpl"]:
                prefixes.add(m["name"])
                continue
            names.add(m["name"])
            if m["kw"] == "import":  # `import a.b, c.d` — every module of the list
                tail = node.value[m.end():].split("\n", 1)[0]
                names |= set(re.findall(r",\s*([A-Za-z_][\w.]*)", tail.split(";", 1)[0]))
            listed = m["paren"] if m["paren"] is not None else m["names"]
            if m["kw"] == "from" and listed:
                names |= {f"{m['name']}.{n}" for n in _imported_names(listed)}
    return names, prefixes


_PYTHONPATH_INI = re.compile(r"^\s*pythonpath\s*=\s*(.+)$", re.MULTILINE)
_CONFIG_IMPORTS = ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini")


def racines_declarees(root: Path) -> list[Path]:
    """Racines d'imports que le dépôt DÉCLARE, au lieu de les laisser deviner.

    Pourquoi. Le critère structurel ci-dessus rate la forme la plus répandue de
    la flotte : des scripts SANS `__init__.py`, rendus importables à l'exécution
    par un `pythonpath =` dans la config pytest ou un `sys.path.insert` dans un
    `conftest.py`. Sous `.claude/`, ils étaient invisibles deux fois — pas de
    paquet, et le sous-arbre élagué au parcours.

    Mesuré le 2026-08-03 sur n8n : **tout** le Python du dépôt vit sous
    `.claude/`. Chaque changement tombait donc sur la règle 6 et rendait la suite
    entière. Le sélecteur était déployé, coûtait du contexte à chaque requête, et
    ne sélectionnait rien — jamais.

    Ce qu'on lit est volontairement LITTÉRAL : des chaînes constantes. Un chemin
    calculé (`str(Path(__file__).parent / x)`) n'est pas résolu, et c'est
    délibéré — il retombe alors sur le repli sûr, pas sur un raté silencieux.
    """
    out: list[Path] = []

    def ajoute(brut: str) -> None:
        brut = brut.strip().strip("\"'")
        if not brut or brut in (".", "./"):
            return
        d = (root / brut).resolve()
        if d.is_dir() and d not in out:
            try:
                d.relative_to(root)
            except ValueError:      # hors du dépôt : hors sujet ici
                return
            out.append(d)

    for nom in _CONFIG_IMPORTS:
        f = root / nom
        try:
            texte = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _PYTHONPATH_INI.finditer(texte):
            valeur = m.group(1).strip()
            if valeur.startswith("["):          # forme TOML : ["a", "b"]
                for tok in re.findall(r"[\"']([^\"']+)[\"']", valeur):
                    ajoute(tok)
            else:                                # forme INI : a b  /  a, b
                for tok in re.split(r"[,\s]+", valeur):
                    ajoute(tok)

    for conf in _trouve_conftests(root):
        try:
            arbre = ast.parse(conf.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError, OSError):
            continue
        for node in ast.walk(arbre):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if not (isinstance(f, ast.Attribute) and f.attr in ("insert", "append")):
                continue
            cible = f.value
            if not (isinstance(cible, ast.Attribute) and cible.attr == "path"
                    and isinstance(cible.value, ast.Name) and cible.value.id == "sys"):
                continue
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    ajoute(a.value)
    return out


def _trouve_conftests(root: Path) -> list[Path]:
    """Les `conftest.py`, y compris sous un dossier en point.

    Le parcours des `.py` élague les dossiers en point ; celui-ci ne le fait pas,
    puisque c'est justement un `conftest.py` sous `.claude/` qui peut déclarer la
    racine à ne pas élaguer. Il ne cherche qu'un nom de fichier, donc il ne lit
    rien : le surcoût est un `listdir`, pas un `stat` par module (F4).
    """
    import os
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PRUNE and d != ".git"
                       and not _copie_imbriquee(dirpath, d)]
        if "conftest.py" in filenames:
            out.append(Path(dirpath) / "conftest.py")
    return out


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


def relative_anchor(mod: str, is_init: bool, level: int) -> list[str]:
    """The package a level-`level` relative import resolves against. Pure.

    R494 — `module_name()` drops `__init__`, so `pkg/sub/__init__.py` is `pkg.sub`, and
    Python resolves its `from ._impl import f` against `pkg.sub` itself. Stripping one
    component as for a plain module gave `pkg._impl`, a module that does not exist, and
    the edge fell back to the parent package. Beyond the top package → [] (unresolved).
    """
    parts = [x for x in mod.split(".") if x]
    anchor = parts if is_init else parts[:-1]
    if level - 1 >= len(anchor):
        return []
    return anchor[:len(anchor) - (level - 1)]


def module_aliases(root: Path, path: Path, roots: list[Path] | None = None) -> set[str]:
    """TOUS les noms sous lesquels un `import` peut désigner ce fichier.

    `module_name` n'en rend qu'un — celui de la racine la plus profonde. C'était
    suffisant tant qu'un dépôt n'écrivait qu'un style de préfixe, et ça ne l'est pas.

    Mesuré le 2026-08-28 sur streaMLytics. `src` est une racine (elle contient des
    paquets), donc `src/utils/x.py` était nommé `utils.x` — mais ce dépôt-ci écrit
    `from src.utils.x import …`, la forme relative à la racine git. Les deux noms ne
    se rencontraient jamais : **59 arêtes retenues sur 979**, 94 % du graphe perdu,
    et tous les tests avec zéro dépendance. Le sélecteur rendait alors un ensemble
    CONSTANT de 19 fichiers, identique pour un collecteur, une vue et un util — dont
    aucun des tests du module modifié.

    C'est le même défaut que celui que `source_roots` a corrigé le 2026-07-30, dans
    l'autre sens : ce jour-là un dépôt écrivait `from app import repo` et la racine
    `src/` a été ajoutée pour lui. Choisir UN nom, quel qu'il soit, casse l'autre
    style. Les indexer tous n'en casse aucun.
    """
    out: set[str] = set()
    for r in (roots or [root]):
        try:
            rel = path.relative_to(r).with_suffix("")
        except ValueError:
            continue
        parts = list(rel.parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        name = ".".join(parts)
        if name and _NOM_IMPORTABLE(name):
            out.add(name)
    return out


def _NOM_IMPORTABLE(mod: str) -> bool:
    """Un `import` peut-il seulement NOMMER ce module ?

    Le critère est celui de Python, pas une liste de dossiers : chaque segment
    doit être un identifiant. `.claude.hooks.observe` échoue sur `.claude` — donc
    aucune ligne d'`import` du dépôt ne peut désigner ce fichier, et l'absence de
    ses importateurs dans le graphe n'est pas une ignorance, c'est un fait.

    C'est ce qui autorise à ne PAS rendre la suite entière pour ces fichiers-là.
    La distinction compte : `hooks.observe` (sans point initial) est importable
    via un paquet-espace-de-noms, donc reste couvert par la règle 6.
    """
    parts = mod.split(".") if mod else []
    return bool(parts) and all(p.isidentifier() for p in parts)


# `vendor/`: a third party's code, its tests needing its own deps (O11, 2026-10-17:
# assistant_perso's test-changed was red only through vendor/hermes-agent — `openai`,
# `prompt_toolkit` absent from the venv). No fleet repo tests a vendor/ of its own.
PRUNE = {".git", ".venv", "venv", "env", "node_modules", "__pycache__",
         "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache",
         "site-packages", ".tox", "htmlcov", ".idea", ".vscode", "vendor"}

# (parent, child) directories that hold a git-ignored FULL copy of the repo: Claude Code
# agent worktrees live under `.claude/worktrees/<name>/`, ignored only by the local
# `.git/info/exclude`, never present in CI. Pruned by PAIR, not by name, so a project
# with its own `worktrees/` package is still walked. Measured 2026-10-04: two such
# copies (118 MB each) under `.claude/`.
NESTED_COPIES = {(".claude", "worktrees")}


def _copie_imbriquee(dirpath: str, d: str) -> bool:
    """Is `dirpath/d` a nested git-ignored copy of the repo?"""
    return (Path(dirpath).name, d) in NESTED_COPIES


def _ignores(root: Path) -> set[str]:
    """Les dossiers que git ignore, en chemins absolus — un seul appel, sans descendre dedans.

    Un test qu'aucun commit ne porte n'est pas un test du dépôt : la CI ne le voit pas.
    Mesuré sur assistant_perso le 2026-10-18 (baseline T96) : `vendor/hermes-agent`, ignoré
    mais absent de PRUNE, a fait choisir 157 tests à un diff de deux hooks — 337 rouges, et
    un push refusé pour un code que personne n'avait touché. Hors dépôt git : rien."""
    r = subprocess.run(["git", "ls-files", "-o", "-i", "--exclude-standard", "--directory"],
                       cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        return set()
    return {str(root / d.rstrip("/")) for d in r.stdout.splitlines() if d.endswith("/")}


def _walk_python(root: Path, roots: list[Path] | None = None,
                 _ignores_: set[str] | None = None) -> list[Path]:
    """Les `.py` du dépôt, en ÉLAGUANT pendant la descente.

    Les dossiers en point restent élagués — SAUF ceux qu'il faut traverser pour
    atteindre une racine d'imports déclarée (`racines_declarees`). Sans cette
    exception, `.claude/hooks/` déclaré dans un `conftest.py` restait invisible
    au graphe alors même que le dépôt affirme l'importer.

    La première version faisait `root.rglob("*.py")` puis filtrait sur
    `p.parts` — donc elle traversait `.venv` en entier avant de le jeter.
    Mesuré sur `trading_bot` (403 modules, sur `/mnt/c`) : **61 s**. C'est F6
    mot pour mot — « un parcours non élagué coûte plus que tout le reste » — et
    F4 explique pourquoi ça fait si mal ici : un `stat` coûte 511× plus cher sur
    `/mnt/c` que sur un disque natif. Un outil censé faire GAGNER du temps avant
    de lancer les tests ne peut pas en coûter une minute.
    """
    import os
    autorises = {str(r) for r in (roots or []) if str(r) != str(root)}
    ignores = _ignores(root) if _ignores_ is None else _ignores_
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        gardes = []
        for d in dirnames:
            if d in PRUNE or _copie_imbriquee(dirpath, d):
                continue
            chemin = str(Path(dirpath) / d)
            if chemin in ignores and not any(
                    a == chemin or a.startswith(chemin + os.sep) for a in autorises):
                continue
            if d.startswith(".") and not any(
                    a == chemin or a.startswith(chemin + os.sep) for a in autorises):
                continue
            gardes.append(d)
        dirnames[:] = gardes
        for f in filenames:
            if f.endswith(".py"):
                out.append(Path(dirpath) / f)
    return out


_SYSPATH_NARROWS = {"remove", "pop"}   # only ever takes a directory away


def _is_sys_path(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "path"
            and isinstance(node.value, ast.Name) and node.value.id == "sys")


def _touches_sys_path(tree: ast.AST) -> bool:
    return any(_is_sys_path(n) for n in ast.walk(tree))


def _scope_names(scopes: list[ast.AST]) -> dict[str, list[ast.AST]]:
    """What each name stands for at a site, outermost scope first: `scopes` is the module,
    then each enclosing function. A scope that assigns a name replaces what the outer one
    said; a parameter or a loop target unsays it, whatever a module-level `=` claims."""
    out: dict[str, list[ast.AST]] = {}
    for scope in scopes:
        here: dict[str, list[ast.AST]] = {}
        unsaid: set[str] = set()
        stack = list(ast.iter_child_nodes(scope))
        while stack:
            n = stack.pop()
            if isinstance(n, ast.arguments):
                unsaid |= {a.arg for a in ast.walk(n) if isinstance(a, ast.arg)}
                continue
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue   # its own scope
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        here.setdefault(t.id, []).append(n.value)
                    else:
                        # `a, b = …` rebinds; `sys.modules[_NAME] = m` only reads `_NAME`.
                        unsaid |= {x.id for x in ast.walk(t) if isinstance(x, ast.Name)
                                   and isinstance(x.ctx, ast.Store)}
            elif (isinstance(n, ast.For) and isinstance(n.target, ast.Name)
                  and isinstance(n.iter, (ast.Tuple, ast.List))):
                here.setdefault(n.target.id, []).extend(n.iter.elts)
            elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension, ast.AugAssign,
                                ast.AnnAssign, ast.NamedExpr)):
                unsaid |= {x.id for x in ast.walk(n.target) if isinstance(x, ast.Name)}
            elif isinstance(n, ast.withitem) and n.optional_vars is not None:
                unsaid |= {x.id for x in ast.walk(n.optional_vars) if isinstance(x, ast.Name)}
            stack.extend(ast.iter_child_nodes(n))
        out.update(here)
        for name in unsaid:
            out.pop(name, None)
        out.update(_param_values(scopes[0], scope))
        out.update(_parametrized(scope))
    return out


def _tails(node: ast.AST, names: dict[str, list[ast.AST]], depth: int = 0,
           here: tuple[str, ...] | None = None) -> set[str] | None:
    """The literal tails of `<anything> / "a" / "b.py"`, or None when the tail is computed.
    An f-string is a pattern: `dir / f"{name}.py"` is `dir/*.py`, every file it can be."""
    if depth > 8:
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        rights = _tails(node.right, names, depth + 1, here)
        if rights is None:
            return None
        anchored = _anchor(node.left, names, here)
        lefts = {"/".join(anchored)} if anchored is not None else (
            _tails(node.left, names, depth + 1, here) or {""})
        return {f"{a}/{b.strip('/')}".strip("/") for a in lefts for b in rights}
    got = _strings(node, names)
    if got is not None:
        return {g.strip("/") for g in got}
    if isinstance(node, ast.JoinedStr):
        # `f"{_NAME}.py"` with `_NAME` a literal is one file. Read as `*`, tools/conftest.py
        # "loaded" all of tools/dev, so every crossroads reached a conftest (T702).
        out = {""}
        for p in node.values:
            said = None
            if isinstance(p, ast.FormattedValue) and p.conversion == -1 and not p.format_spec:
                said = _strings(p.value, names)
            vals = {p.value} if isinstance(p, ast.Constant) else set(said or ("*",))
            out = {a + b for a in out for b in vals}
        return out
    if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Path"
            and len(node.args) == 1):
        return _tails(node.args[0], names, depth + 1, here)
    if isinstance(node, ast.Name) and node.id in names:
        vals = [_tails(v, names, depth + 1, here) for v in names[node.id]]
        return None if any(v is None for v in vals) else set().union(*vals)
    return None


def _param_values(tree: ast.AST, fn: ast.AST) -> dict[str, list[ast.AST]]:
    """{parameter of `fn`: what each call in this file passes}, for a private function called
    only by its name, positionally. Anything else about it, and it says nothing."""
    if not (isinstance(fn, ast.FunctionDef) and fn.name.startswith("_")) or fn.args.vararg \
            or fn.args.kwarg or fn.args.kwonlyargs or fn.args.defaults:
        return {}
    params = [a.arg for a in fn.args.args]
    calls: list[ast.Call] = []
    uses = 0
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id == fn.name:
            uses += 1
        elif isinstance(n, ast.Attribute) and n.attr == fn.name:
            return {}
        elif isinstance(n, ast.Call) and getattr(n.func, "id", "") == fn.name:
            calls.append(n)
    if not calls or uses != len(calls) or any(
            len(c.args) != len(params) or c.keywords
            or any(isinstance(a, ast.Starred) for a in c.args) for c in calls):
        return {}
    return {p: [c.args[i] for c in calls] for i, p in enumerate(params)}


def _parametrized(fn: ast.AST) -> dict[str, list[ast.AST]]:
    """{parameter: its values}, for `@pytest.mark.parametrize("x", [literal, …])`."""
    out: dict[str, list[ast.AST]] = {}
    for d in getattr(fn, "decorator_list", ()):
        if (isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "parametrize"
                and len(d.args) >= 2 and isinstance(d.args[0], ast.Constant)
                and isinstance(d.args[0].value, str) and "," not in d.args[0].value
                and isinstance(d.args[1], (ast.List, ast.Tuple))):
            out[d.args[0].value.strip()] = list(d.args[1].elts)
    return out


def _enclosing(site: ast.AST, parents: dict[ast.AST, ast.AST], tree: ast.AST) -> list[ast.AST]:
    """The scopes a site sees, module first."""
    chain: list[ast.AST] = []
    up = parents.get(site)
    while up is not None:
        if isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            chain.append(up)
        up = parents.get(up)
    return [tree] + chain[::-1]


def _inserted_dirs(arg: ast.AST, names: dict[str, list[ast.AST]], here: tuple[str, ...],
                   depth: int = 0) -> set[str | None]:
    """What `sys.path.insert(0, ARG)` designates: `str()` unwrapped, a name followed through
    its assignments in scope, and, past `Path(__file__)`, the literal tail of a path built on
    a parameter (`repo / "tools/dev"`: `_load_paths` says why that is enough). T702."""
    if depth > 8:
        return {_UNKNOWN}
    if isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "str" and len(arg.args) == 1:
        return _inserted_dirs(arg.args[0], names, here, depth + 1)
    if isinstance(arg, ast.Name) and arg.id in names:
        return set().union(*(_inserted_dirs(v, names, here, depth + 1) for v in names[arg.id]))
    exact = _literal_paths(arg, names, {}, here)
    if _UNKNOWN not in exact:
        return exact
    if isinstance(arg, ast.Attribute) and arg.attr == "parent":
        above = _inserted_dirs(arg.value, names, here, depth + 1)
        return {_UNKNOWN} if _UNKNOWN in above else {d.rpartition("/")[0] for d in above}
    tails = _tails(arg, names)
    return tails if tails and all(tails) else {_UNKNOWN}


def _only_reads_or_restores(node: ast.AST, up: ast.AST | None,
                            parents: dict[ast.AST, ast.AST]) -> bool:
    """`sys.path[:]` and `list(sys.path)` copy it, a loop reads it, `sys.path[:] = saved` puts
    a copy back: none of them adds a directory. `sys.path[:] = other` with `other` built
    from anything else than a name or a filter of `sys.path` itself stays unread."""
    if isinstance(up, ast.Call) and getattr(up.func, "id", "") == "list" and up.args == [node]:
        return True
    if isinstance(up, (ast.comprehension, ast.For)) and up.iter is node:
        return True
    if not (isinstance(up, ast.Subscript) and up.value is node and isinstance(up.slice, ast.Slice)
            and up.slice.lower is None and up.slice.upper is None):
        return False
    if isinstance(up.ctx, ast.Load):
        return True
    assign = parents.get(up)
    if not isinstance(assign, ast.Assign):
        return False
    value = assign.value
    return isinstance(value, ast.Name) or (
        isinstance(value, ast.ListComp) and _is_sys_path(value.generators[0].iter))


def _only_absent_is_wrong(tree: ast.AST, p: Path, root: Path) -> bool:
    """Would this file resolve if the directories it names existed?"""
    class Everything(type(root)):
        def is_dir(self):
            return True
    return syspath_inserts(tree, p.relative_to(root).as_posix(), Everything(root))[1]


def _names_tmp_path(arg: ast.AST) -> bool:
    if isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "str" and len(arg.args) == 1:
        arg = arg.args[0]
    return isinstance(arg, ast.Name) and arg.id == "tmp_path"


def syspath_inserts(tree: ast.AST, rel: str, root: Path,
                    absent: set[str] | None = None) -> tuple[set[str], bool]:
    """(repo-relative directories this file puts on `sys.path`, fully resolved?).

    2026-10-20: every file that touched `sys.path` was `dynamic`, so 90 of 109 tests here
    and 246 of 880 in streamlytics were picked on every diff, whatever changed. Most of
    them insert a directory the source states (`ROOT / "tools" / "dev"`). That directory
    is resolved here, and the file's imports are resolved THROUGH it (`_build_graph`): the
    edge exists, so the blanket flag is no longer needed for that file.

    Resolved means EVERY use of `sys.path` in the file is one of:
      - the receiver of `.insert(i, D)` / `.append(D)` whose `D` resolves (`_literal_paths`,
        `str(...)` unwrapped) to directories that EXIST inside the repository;
      - the receiver of `.remove(...)` / `.pop(...)`: it can only narrow what is importable;
      - the right side of `x in sys.path` / `x not in sys.path`.
    Anything else (`sys.path[:0] = …`, `.extend`, `sys.path = …`, `sys.path` passed as an
    argument, an unresolvable or missing directory) returns False: the file stays
    `dynamic`, the safe fallback. A miss here costs over-selection, never a false green.
    `absent` collects the directories that resolved but do not exist here."""
    if not _touches_sys_path(tree):     # most files: skip the parent map (4x slower otherwise)
        return set(), True
    parents: dict[ast.AST, ast.AST] = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parents[c] = n
    here = tuple(rel.split("/"))
    dirs: set[str] = set()
    ok = True
    for node in ast.walk(tree):
        if not _is_sys_path(node):
            continue
        up = parents.get(node)
        call = parents.get(up) if up is not None else None
        if (isinstance(up, ast.Attribute) and up.value is node and isinstance(call, ast.Call)
                and call.func is up):
            if up.attr in _SYSPATH_NARROWS:
                continue
            if up.attr in ("insert", "append") and not call.keywords:
                args = call.args[1:] if up.attr == "insert" else call.args
                if len(args) != 1:
                    ok = False
                    continue
                if _names_tmp_path(args[0]):
                    continue    # a pytest scratch directory: no file of this repository
                for d in _inserted_dirs(args[0], _scope_names(_enclosing(call, parents, tree)),
                                        here):
                    if d is not _UNKNOWN and absent is not None and not (root / d).is_dir():
                        absent.add(d)
                    if d is _UNKNOWN or not (root / d).is_dir():
                        ok = False
                    else:
                        dirs.add(d)
                continue
            ok = False      # extend, clear, sort, …: what it adds is not read
            continue
        if (isinstance(up, ast.Compare) and node in up.comparators
                and all(isinstance(o, (ast.In, ast.NotIn)) for o in up.ops)):
            continue
        if _only_reads_or_restores(node, up, parents):
            continue
        ok = False          # sys.path[...] = …, sys.path = …, f(sys.path), …
    return dirs, ok


def _resolve_in_dirs(name: str, dirs: list[Path], canon_of: dict[Path, str]) -> set[str]:
    """Every in-repo module `import name` can load from `dirs`, packages included. Pure.

    `import a.b` executes `a/__init__.py` too, and `from a import sym` names `a.sym`: every
    dotted prefix is tried, each against `D/x.py` and `D/x/__init__.py`. Over-approximate on
    purpose: an extra edge costs a test, a missing one the guarantee."""
    parts = [p for p in name.split(".") if p]
    out: set[str] = set()
    for d in dirs:
        for i in range(1, len(parts) + 1):
            base = d.joinpath(*parts[:i])
            for cand in (base.parent / (base.name + ".py"), base / "__init__.py"):
                if cand in canon_of:
                    out.add(canon_of[cand])
    return out


def build_graph(root: Path,
                roots: list[Path] | None = None,
                ) -> tuple[dict[str, set[str]], set[str], list[str], dict[str, Path]]:
    """(module -> modules importés), modules dynamiques, non parsables, module -> chemin.

    `roots` est passé par l'appelant pour n'être calculé qu'UNE fois : sa
    découverte parcourt l'arbre à la recherche des `conftest.py`, et un parcours
    de plus coûte ici plus cher que tout le reste (F4 — un `stat` sur `/mnt/c`).
    """
    return _build_graph(root, roots)[:4]


def _importlib_aliases(tree: ast.AST) -> tuple[dict[str, str], bool]:
    """({local name: the `importlib` path it stands for}, a star import seen?)."""
    aliases: dict[str, str] = {}
    star = False
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == "importlib" or a.name.startswith("importlib."):
                    aliases[a.asname or "importlib"] = a.name if a.asname else "importlib"
        elif isinstance(n, ast.ImportFrom) and not n.level and n.module and (
                n.module == "importlib" or n.module.startswith("importlib.")):
            for a in n.names:
                star = star or a.name == "*"
                aliases[a.asname or a.name] = f"{n.module}.{a.name}"
    return aliases, star


def _load_paths(arg: ast.AST, names: dict[str, list[ast.AST]],
                here: tuple[str, ...], depth: int = 0) -> set[str] | None:
    """Repo-relative files `spec_from_file_location` is given, or None if unstated.

    `root / "tools/x.py"`, with `root` a parameter, says which file of WHICHEVER repository:
    in this one it is `tools/x.py`, and elsewhere a diff here cannot change it. So a literal
    tail is enough; `importlib_loads` refuses it if no such file exists (`tmp / "x.py"`)."""
    if isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "str" and len(arg.args) == 1:
        arg = arg.args[0]
    if (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute)
            and arg.func.attr == "with_name" and len(arg.args) == 1):
        base = _anchor(arg.func.value, names, here)
        sibling = _strings(arg.args[0], names)
        if base is None or not sibling:
            return None
        return {"/".join(base[:-1] + (s,)) for s in sibling}
    if isinstance(arg, ast.Name) and arg.id in names:
        if depth > 8:
            return None    # `path = path.parent`: a name that says itself says nothing
        vals = [_load_paths(v, names, here, depth + 1) for v in names[arg.id]]
        return None if any(v is None for v in vals) else set().union(*vals)
    exact = _literal_paths(arg, names, {}, here)
    if _UNKNOWN not in exact:
        return exact
    tails = _tails(arg, names, 0, here)
    # A bare `f"{x}.py"` says nothing of where: not a tail, an unknown.
    return None if tails is None or any("*" in t and "/" not in t for t in tails) else tails


def dunder_imports(tree: ast.AST) -> tuple[set[str], bool]:
    """(modules named by `__import__("x")`, any other use of `__import__`?). T702: 17 files
    wrote `__import__("time")` for a one-off stdlib call, and all 17 were picked on every
    diff; a literal is an `import` written differently, `test_fleet_apply` alone is 254 s."""
    named: set[str] = set()
    def self_(a: ast.expr) -> bool:
        return isinstance(a, ast.Name) and a.id == "__name__"

    calls = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)
             and len(n.args) == 1 and not n.keywords
             and (self_(n.args[0]) or (isinstance(n.args[0], ast.Constant)
                                       and isinstance(n.args[0].value, str)))}
    other = False
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and id(n.func) in calls \
                and getattr(n.func, "id", "") == "__import__":
            if not self_(n.args[0]):
                named.add(n.args[0].value)
        elif isinstance(n, ast.Name) and n.id == "__import__" and id(n) not in calls:
            other = True
    return named, other


def importlib_loads(tree: ast.AST, rel: str) -> tuple[set[str], set[str], bool]:
    """(module names, repo-relative files this file loads through `importlib`, opaque?).

    T702, 2026-11-04: every use of `importlib` made a file `dynamic`, and `_build_graph`
    widens that to each resolved `sys.path` file reaching it. `find_spec("xdist")` in
    `blast_radius.py` loads nothing, yet 134 of 213 tests were picked on every diff:
    `devtime_report.py` alone reached 1 test by the graph and selected 142.

    Read here, each site is one of:
      - it locates or describes, and loads no code of ours: `importlib.metadata.*`,
        `module_from_spec`, `find_spec` (unless its result reaches a loader other than
        through a stated module: then `import_module`'s name says what is loaded, and any
        other spec executed is judged at the site that built it, see below);
      - it loads what the source states: `import_module("x")`,
        `spec_from_file_location(n, ROOT / "a" / "b.py")`. That is an edge, as `import x`;
      - it re-reads a module already imported: `spec_from_file_location(n, m.gf.__file__)`,
        the graph has that edge from the `import` itself;
      - anything else: opaque. A computed name or path, `reload`, `importlib` passed as a
        value, a `*` import, a loader built by hand.
    Opaque keeps the old behaviour, `dynamic`. A miss here costs over-selection, never a
    false green; a path read wrong would cost a false green, hence `_scope_names`."""
    aliases, star = _importlib_aliases(tree)
    if not aliases:
        return set(), set(), False
    parents: dict[ast.AST, ast.AST] = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parents[c] = n
    here = tuple(rel.split("/"))
    loaded: set[str] = set()
    files: set[str] = set()
    opaque = star
    imported_names = {(a.asname or a.name).split(".")[0] for n in ast.walk(tree)
                      if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}

    def names_at(site: ast.AST) -> dict[str, list[ast.AST]]:
        return _scope_names(_enclosing(site, parents, tree))

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Name) and node.id in aliases
                and isinstance(node.ctx, ast.Load)):
            continue
        top: ast.AST = node
        dotted = aliases[node.id]
        while isinstance(parents.get(top), ast.Attribute) and parents[top].value is top:
            top = parents[top]
            dotted += "." + top.attr
        call = parents.get(top)
        called = isinstance(call, ast.Call) and call.func is top
        if dotted.startswith("importlib.metadata") or dotted == "importlib.util.module_from_spec":
            continue
        if dotted == "importlib.reload" and called and len(call.args) == 1 \
                and isinstance(call.args[0], ast.Name) and call.args[0].id in imported_names:
            continue   # the graph has that edge from the `import` itself
        if dotted == "importlib.util" and isinstance(call, ast.Call) \
                and getattr(call.func, "attr", "") == "setattr":
            continue   # a test stubbing `find_spec`: it narrows, it loads nothing
        if dotted == "importlib.util.find_spec" and called:
            # A spec found by a stated name is an edge, as `import x`. By a computed name,
            # only a yes/no is safe: a spec kept may reach a loader nothing here reads.
            got = _strings(call.args[0], names_at(call)) if call.args else None
            if got is not None:
                loaded |= set(got)
            elif not isinstance(parents.get(call), (ast.IfExp, ast.If, ast.Compare, ast.UnaryOp,
                                                    ast.BoolOp, ast.Assert)):
                opaque = True
        elif dotted == "importlib.import_module" and called and len(call.args) == 1 \
                and not call.keywords:
            got = _strings(call.args[0], names_at(call))
            if got is None or any(g.startswith(".") for g in got):
                opaque = True
            else:
                loaded |= set(got)
        elif dotted == "importlib.util.spec_from_file_location" and called \
                and len(call.args) >= 2:
            arg = call.args[1]
            if isinstance(arg, ast.Attribute) and arg.attr == "__file__":
                continue
            paths = _load_paths(arg, names_at(call), here)
            if paths is None:
                opaque = True
            else:
                files |= paths
        else:
            opaque = True
    return loaded, files, opaque


_INSERT_ROUNDS = 3   # a directory found only through a file found only through an insert…


def _build_graph(root: Path, roots: list[Path] | None = None):
    """`build_graph`, plus the modules that entered the graph ONLY through a `sys.path` insert.

    Two phases, because the directories files insert are known only once they are parsed:
    (1) walk with the global roots and parse every file, collecting its resolved inserts;
    (2) walk again with every inserted directory allowed (`.claude/scripts` is a dot
    directory the first walk prunes), and repeat for the files that appear, up to
    `_INSERT_ROUNDS` times; (3) only then build `known`, the aliases and the per-file
    resolution. The inserted directories are NEVER global roots: `known` and the aliases
    collide on a basename two directories share (`select_tests.py` lives in `tools/dev`
    AND in `config-optimale/.claude/scripts`). Resolution through them is per file.

    The fifth element names those modules: dependency nodes, never test candidates
    (R305: a test hidden by a dot or by `.gitignore`, once selected, fails to import)."""
    roots = roots or source_roots(root)
    ignores = _ignores(root)
    trees: dict[Path, ast.AST | None] = {}
    inserted: dict[Path, set[str]] = {}
    unresolved_sp: set[Path] = set()
    absent_sp: set[Path] = set()
    touches: set[Path] = set()
    extra: set[str] = set()
    base_walk: set[Path] | None = None
    py: list[Path] = []
    for _ in range(_INSERT_ROUNDS + 1):
        py = _walk_python(root, list(roots) + [root / d for d in sorted(extra) if d],
                          _ignores_=ignores)
        if base_walk is None:
            base_walk = set(py)
        for p in py:
            if p in trees:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(text)
            except (SyntaxError, ValueError, OSError):
                trees[p] = None
                continue
            trees[p] = tree
            # `sys.path` is an attribute named `path`: no such word, no use — and no walk.
            if "path" not in text or not _touches_sys_path(tree):
                inserted[p] = set()
                continue
            touches.add(p)
            absent: set[str] = set()
            dirs, ok = syspath_inserts(tree, p.relative_to(root).as_posix(), root, absent)
            inserted[p] = dirs
            if not ok:
                unresolved_sp.add(p)
                if absent and _only_absent_is_wrong(tree, p, root):
                    absent_sp.add(p)
        wanted = set().union(*inserted.values()) if inserted else set()
        if wanted <= extra:
            break
        extra |= wanted
    walked = {d for d in extra}
    for p, dirs in inserted.items():   # bound hit: an insert never walked stays dynamic
        if not dirs <= walked:
            unresolved_sp.add(p)

    canon_of = {p: module_name(root, p, roots) for p in py}
    known = {canon_of[p]: p for p in py}
    canon_by_rel = {p.relative_to(root).as_posix(): canon_of[p] for p in py}
    dependency_only = {canon_of[p] for p in py if p not in (base_walk or set())}
    # Un fichier, plusieurs noms possibles selon la racine par laquelle on l'importe.
    # `known` reste la carte CANONIQUE (un nom, celui du graphe) ; cet index-ci relie
    # chaque alias à ce nom canonique, et c'est lui qui résout les `import`.
    alias: dict[str, str] = {}
    for p in py:
        canon = canon_of[p]
        for a in module_aliases(root, p, roots):
            alias.setdefault(a, canon)
    imports: dict[str, set[str]] = {}
    dynamic: set[str] = set()
    only_absent: set[str] = set()   # `dynamic` for one reason: a directory that does not exist
    unparsable: list[str] = []

    for p in py:
        mod = canon_of[p]
        tree = trees.get(p)
        if tree is None:
            unparsable.append(str(p.relative_to(root)))
            continue
        if p in unresolved_sp:
            # `sys.path` touched in a way `syspath_inserts` cannot read: after it, `import x`
            # can designate a file no static edge links to this module.
            dynamic.add(mod)
            if p in absent_sp:
                only_absent.add(mod)
        got: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    got.add(a.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relatif : résoudre contre le paquet du fichier
                    pkg = relative_anchor(mod, p.name == "__init__.py", node.level)
                    prefix = ".".join(pkg + ([node.module] if node.module else []))
                else:
                    prefix = node.module or ""
                got.add(prefix)
                for a in node.names:
                    got.add(f"{prefix}.{a.name}" if prefix else a.name)
        spelled, unspelled = dunder_imports(tree)
        got |= spelled
        if unspelled:
            dynamic.add(mod)
            only_absent.discard(mod)
        loaded_names, loaded_files, opaque = importlib_loads(tree, p.relative_to(root).as_posix())
        got |= loaded_names
        # A tail may follow a computed folder (`ROOT / copy / "x.py"`): every file it can be.
        # No such file here (`root / "hooks/_verdict.py"`, another repository's): no
        # diff here reaches it. A file on disk the walk pruned: no edge can say so, `dynamic`.
        matching_files = {r for f in loaded_files for r in canon_by_rel
                          if fnmatch.fnmatchcase(r, f) or fnmatch.fnmatchcase(r, "*/" + f)}
        if opaque or any(f not in canon_by_rel and (root / f).exists() for f in loaded_files):
            dynamic.add(mod)
            only_absent.discard(mod)
        in_strings, templated = imports_in_strings(tree)
        got |= in_strings
        for prefix in templated:
            got |= {a for a in alias if a.startswith(prefix + ".")}

        # On ne garde que ce qui existe DANS le dépôt ; le reste est une
        # dépendance tierce, dont on ne suit pas les modifications ici.
        resolved = set()
        for name in got:
            if name in alias:
                resolved.add(alias[name])
            else:
                # `from a.b import c` où c est un symbole : a.b est le module.
                head = name.rsplit(".", 1)[0]
                if head in alias:
                    resolved.add(alias[head])
        # ADDED to the global resolution, never in place of it: the directories this file
        # puts on `sys.path`, and its own directory. A script run as `python tools/dev/a.py`
        # imports its sibling `b` with no package; 84/84 bare sibling imports in tools/dev
        # and .claude/scripts here, 46/46 in streamlytics, had no edge (2026-10-20).
        local = [p.parent] + [root / d if d else root for d in sorted(inserted.get(p, ()))]
        for name in got:
            resolved |= _resolve_in_dirs(name, local, canon_of)
        for f in matching_files:
            resolved.add(canon_by_rel[f])
        resolved.discard(mod)
        imports[mod] = resolved

    # Released from `dynamic` only if what it imports is static too. A file that touched
    # `sys.path` was always picked; once its inserts resolve, the graph alone selects it —
    # and the graph does not see what an `importlib` module it imports loads. Measured
    # 2026-10-20: 10 tests here, 46 in streamlytics, would have lost their only selection.
    # (Tests that never touched `sys.path` and reach such a module are not widened here.)
    released = {canon_of[p] for p in touches if p not in unresolved_sp}
    # A directory that does not exist hides no file: the module itself stays `dynamic`, its
    # importers have nothing more to see (`presets/…/roadmap_health.py` names `tools/dev` as
    # deployed; through it test_fleet_apply, 254 s, was picked on every diff. T702).
    reaching = importers_closure(imports, dynamic - only_absent)
    dynamic |= released & reaching

    return imports, dynamic, unparsable, known, dependency_only


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


def tests_mentioning(root: Path, changed: list[str], all_tests: set[str],
                     known: dict[str, Path] | None = None) -> set[str]:
    """Tests qui NOMMENT un fichier modifié en clair — invocation par `subprocess`.

    L'angle mort que ceci ferme. Un test qui lance un script par `subprocess`
    plutôt que de l'importer n'apparaît dans AUCUN graphe d'imports : le script
    peut changer complètement, le test qui l'exerce ne sera pas sélectionné, et
    la suite réduite rendra un vert qui ne veut rien dire — le mode de
    défaillance que l'en-tête de ce fichier déclare pire que pas de sélecteur.

    Constaté le 2026-08-03 sur un déploiement : le seul test du dépôt
    n'importait rien et appelait `guard_destructive.py` et `audit_runner.py` en
    sous-processus. Il n'était sauvé que par accident — ces fichiers vivent sous
    `.claude/`, ce qui déclenchait la règle 6. Sortir l'un d'eux de `.claude/`
    aurait suffi à le rendre invisible.

    La détection est textuelle et volontairement large : on cherche le nom de
    base du fichier modifié dans la source du test. Elle ne peut qu'ÉLARGIR la
    sélection, jamais la réduire — un faux positif coûte un test de trop, un
    faux négatif coûte la garantie.
    """
    if known is None:                       # appel isolé : on refait le graphe
        known = build_graph(root)[3]
    names = {Path(c).name for c in changed}
    paths = {c.replace("\\", "/") for c in changed}
    hits: set[str] = set()
    for mod, p in known.items():
        if mod not in all_tests:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:          # illisible : on ne peut rien conclure, donc on prend
            hits.add(mod)
            continue
        if any(n in text for n in names) or any(q in text for q in paths):
            hits.add(mod)
    return hits


def tests_reading_the_directory(changed: list[str], all_tests: set[str],
                                known: dict[str, Path]) -> set[str]:
    """Tests that NAME the directory of a changed non-Python file.

    A test that reads `sorted((ROOT / ".claude" / "dev-docs").glob("*.md"))` never
    names the file that changed — only its folder, sometimes split into path parts.
    Matching the last directory component catches both spellings. A file at the repo
    root has no folder to name: only its own name (`tests_mentioning`) selects for it.
    Broad on purpose, like the mention rule: a false positive costs one test.
    """
    dossiers = {Path(c).parent.name for c in changed} - {""}
    if not dossiers:
        return set()
    hits: set[str] = set()
    for mod, p in known.items():
        if mod not in all_tests:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            hits.add(mod)
            continue
        if any(f'"{d}"' in text or f"'{d}'" in text or f"{d}/" in text for d in dossiers):
            hits.add(mod)
    return hits


_SCANS_TEST_FILES = re.compile(r"""glob\(\s*["']test_\*\.py["']\s*\)""")


def tests_scanning_the_test_files(changed: list[str], all_tests: set[str],
                                  known: dict[str, Path]) -> set[str]:
    """Meta-guards that walk `tests/` — selected whenever a TEST file changes.

    A guard like `_TESTS.glob("test_*.py")` judges every test file (no text
    assertion on source, no `.py` path read by text, every proof calling its
    detector…). It imports nothing the changed test imports and names neither the
    file nor, usually, its folder: the three rules above never pick it. Measured on
    2026-09-26: a fixture literal `"kpi_helpers.py"` added to one test passed
    `make test-changed` green and was caught one commit later by
    `test_a_guard_reads_structure_not_text`, selected by accident. 17 files scan
    this way.
    """
    if not any(is_test(c) for c in changed):
        return set()
    hits: set[str] = set()
    for mod, p in known.items():
        if mod not in all_tests:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            hits.add(mod)
            continue
        if _SCANS_TEST_FILES.search(text):
            hits.add(mod)
    return hits


# Tree scanners: a guard that walks a directory of `.py` files (`rglob("*.py")`,
# `glob("**/*.py")`, `os.walk`) reads every file under it and imports none of them, so
# the import graph never reaches it. The meta-guard rule above only knew the literal
# `glob("test_*.py")` — a FORM — and missed the property: code-critic reproduced it on
# 2026-09-26 with a naive-datetime guard (`_ROOT.rglob("*.py")`) that `select_tests` left
# out when `app/jobs.py` gained a `datetime.now()`. The directory walked is resolved
# statically: literals, names bound to them (module-level or local, a name assigned twice
# standing for both), loop variables over a tuple, and `Path(__file__)` anchors resolved
# from the test file's OWN location (`.parent`, `.parents[k]`). Anything unresolvable is
# the whole repository — and stays so when a literal is joined to it: code-critic's
# second finding, where `Path(__file__).parent / "fixtures"` in `tests/foo/` had resolved
# to a top-level `fixtures/` because « root » and « unknown » shared one value.
_TREE_SCAN_HINT = re.compile(
    r"\.rglob\(|\.glob\(|\.iterdir\(|\bos\.(?:walk|listdir|scandir)\(|\brepo_files\(")
_UNKNOWN = None   # the whole repository — never joined to anything


def _strings(node: ast.AST, names: dict[str, list[ast.AST]], depth: int = 0) -> list[str] | None:
    """The string constants a name or literal collection stands for, or None."""
    if depth > 8:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        vals = [_strings(e, names, depth + 1) for e in node.elts]
        return None if any(v is None for v in vals) else [x for v in vals for x in v]
    if isinstance(node, ast.Name) and node.id in names:
        vals = [_strings(v, names, depth + 1) for v in names[node.id]]
        return None if any(v is None for v in vals) else [x for v in vals for x in v]
    return None


def _up(parts: tuple[str, ...] | None, levels: int) -> tuple[str, ...] | None:
    if parts is None or levels > len(parts):
        return None   # above the repository: unknown
    return parts[:len(parts) - levels]


def _anchor(node: ast.AST, names: dict[str, list[ast.AST]], here: tuple[str, ...] | None,
            depth: int = 0) -> tuple[str, ...] | None:
    """Repo-relative parts of a `Path(__file__)`-derived expression, or None."""
    if depth > 8 or here is None:
        return None
    if isinstance(node, ast.Call):
        if (getattr(node.func, "id", "") == "Path" or getattr(node.func, "attr", "") == "Path") \
                and node.args and getattr(node.args[0], "id", "") == "__file__":
            return here
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("resolve", "absolute"):
            return _anchor(node.func.value, names, here, depth + 1)
        return None
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        return _up(_anchor(node.value, names, here, depth + 1), 1)
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute)
            and node.value.attr == "parents" and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, int)):
        return _up(_anchor(node.value.value, names, here, depth + 1), node.slice.value + 1)
    if isinstance(node, ast.Name) and len(names.get(node.id, ())) == 1:
        return _anchor(names[node.id][0], names, here, depth + 1)
    return None


def _literal_paths(node: ast.AST, names: dict[str, list[ast.AST]], loops: dict[str, ast.AST],
                   here: tuple[str, ...] | None, depth: int = 0) -> set[str | None]:
    """Repo-relative directories an expression designates ("" = the repo root itself);
    `_UNKNOWN` when it cannot be resolved."""
    if depth > 8:
        return {_UNKNOWN}
    anchored = _anchor(node, names, here)
    if anchored is not None:
        return {"/".join(anchored)}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        lefts = _literal_paths(node.left, names, loops, here, depth + 1)
        rights = _strings(node.right, names)
        if rights is None and isinstance(node.right, ast.Name) and node.right.id in loops:
            rights = _strings(loops[node.right.id], names)
        if rights is None or _UNKNOWN in lefts:
            return lefts if rights is not None else {_UNKNOWN}
        return {f"{a}/{b.strip('/')}".strip("/") for a in lefts for b in rights}
    if isinstance(node, ast.Name) and node.id in names:
        return set().union(*(_literal_paths(v, names, loops, here, depth + 1)
                             for v in names[node.id]))
    if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Path" and node.args
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
            and not node.args[0].value.startswith("/")):
        return {node.args[0].value.strip("/").lstrip("./")}
    return {_UNKNOWN}


def scanned_patterns(source: str, rel: str | None = None) -> set[tuple[str | None, str, bool]]:
    """(directory, name pattern, recursive) for every directory walk in this test. Pure.

    R338 (2026-09-29): `scanned_directories` knew three FORMS — `rglob("*.py")`,
    `glob("**…py")`, `os.walk` — and a sweep tracing every file the suite opens found ~45
    tests it missed: `glob("*.py")` over `airflow/dags/`, `iterdir()` over the views,
    `rglob("*.md")` over `.claude/dev-docs/`, `glob("docker-compose*.y*ml")` at the root.
    The property is « this test reads the files under D matching P »: every walk counts,
    whatever its pattern, and a change selects the test when it falls under D and matches P
    (code-critic R338: containment of the RESOLVED directory, never a name match).
    `directory` is `_UNKNOWN` when it cannot be resolved — then only the pattern decides."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return _walks_in(tree, tree, rel)


def _walks_in(tree: ast.AST, site: ast.AST,
              rel: str | None) -> set[tuple[str | None, str, bool]]:
    """`scanned_patterns` of the walks written inside `site`, names read from the whole file."""
    names: dict[str, list[ast.AST]] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names.setdefault(t.id, []).append(n.value)
    loops = {n.target.id: n.iter for n in ast.walk(tree)
             if isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.target, ast.Name)}
    here = tuple(rel.split("/")) if rel else None
    out: set[tuple[str | None, str, bool]] = set()
    for n in ast.walk(site):
        if isinstance(n, ast.Call) and _callee(n) == "repo_files":
            out |= _repo_files_walk(n, names, loops)
            continue
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        attr = n.func.attr
        pattern = (n.args[0].value if n.args and isinstance(n.args[0], ast.Constant)
                   and isinstance(n.args[0].value, str) else None)
        if attr == "rglob":
            dirs, pat, rec = _literal_paths(n.func.value, names, loops, here), pattern or "*", True
        elif attr == "glob" and n.args:
            pat = pattern or "*"
            rec = pat.startswith("**")
            pat = pat.split("/")[-1] if rec else pat
            if "/" in pat:            # `glob("sub/*.py")`: resolve the fixed prefix
                head, pat = pat.rsplit("/", 1)
                dirs = {(f"{d}/{head}".strip("/") if d is not _UNKNOWN else _UNKNOWN)
                        for d in _literal_paths(n.func.value, names, loops, here)}
            else:
                dirs = _literal_paths(n.func.value, names, loops, here)
        elif attr == "iterdir" and not n.args:
            dirs, pat, rec = _literal_paths(n.func.value, names, loops, here), "*", False
        elif attr in ("listdir", "scandir") and getattr(n.func.value, "id", "") == "os" \
                and n.args:
            dirs, pat, rec = _literal_paths(n.args[0], names, loops, here), "*", False
        elif attr == "walk" and getattr(n.func.value, "id", "") == "os" and n.args:
            dirs, pat, rec = _literal_paths(n.args[0], names, loops, here), "*", True
        else:
            continue
        out |= {(d, pat, rec) for d in dirs}
    return out


def _callee(call: ast.Call) -> str:
    f = call.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


def _repo_files_walk(n: ast.Call, names: dict[str, list[ast.AST]],
                     loops: dict[str, ast.AST]) -> set[tuple[str | None, str, bool]]:
    """`tools/dev/repo_files.repo_files(root, pattern, under=…)` is a recursive walk.

    Its contract is « `root` is the repository, `under` is repo-relative », so the walked
    directory is `under` alone (the repo root without it). `root` is a parameter in every
    caller — so a guard can pass a `tmp_path` repo — and resolving it would always give
    `_UNKNOWN`. Added 2026-10-04 when four guards moved off `rglob` onto it: without
    this branch `make test-changed` stopped selecting them."""
    args = list(n.args)
    kw = {k.arg: k.value for k in n.keywords if k.arg}
    pat_node = args[1] if len(args) > 1 else kw.get("pattern")
    pat = (pat_node.value if isinstance(pat_node, ast.Constant)
           and isinstance(pat_node.value, str) else "*")
    under = args[2] if len(args) > 2 else kw.get("under")
    if under is None:
        return {("", pat, True)}
    vals = _strings(under, names)
    if vals is None and isinstance(under, ast.Name) and under.id in loops:
        vals = _strings(loops[under.id], names)
    if vals is None:
        return {(_UNKNOWN, pat, True)}
    return {("" if v in (".", "./") else v.strip("/"), pat, True) for v in vals}


def scanned_directories(source: str, rel: str | None = None) -> set[str | None]:
    """Repo-relative directories whose `.py` files this test walks. Pure.

    Kept for its callers and self-tests: the `.py` walks among `scanned_patterns`."""
    return {d for d, pat, _ in scanned_patterns(source, rel) if fnmatch.fnmatch("x.py", pat)}


def _walk_matches(d: str | None, pat: str, rec: bool, c: str) -> bool:
    """Does changed path `c` fall under walk (d, pat, rec)? Pure."""
    name = c.rsplit("/", 1)[-1]
    if not fnmatch.fnmatch(name, pat):
        return False
    if d is _UNKNOWN:
        return True
    parent = c.rsplit("/", 1)[0] if "/" in c else ""
    if rec:
        return d == "" or parent == d or parent.startswith(d + "/")
    return parent == d


def tests_scanning_the_tree(changed: list[str], all_tests: set[str],
                            known: dict[str, Path], root: Path | None = None) -> set[str]:
    """Tests that walk a directory in which a changed file falls, pattern included (R338)."""
    if not changed:
        return set()
    hits: set[str] = set()
    for mod, path in known.items():
        if mod not in all_tests:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            hits.add(mod)
            continue
        if not _TREE_SCAN_HINT.search(text):
            continue
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix() if root else None
        except ValueError:
            rel = None
        if any(_walk_matches(d, pat, rec, c)
               for d, pat, rec in scanned_patterns(text, rel) for c in changed):
            hits.add(mod)
    return hits


_LISTS_THE_REPOSITORY = re.compile(r"""["']ls-files["']""")


def tests_listing_the_repository(any_change: bool, all_tests: set[str],
                                 known: dict[str, Path]) -> set[str]:
    """Tests whose input is `git ls-files` — selected on ANY change.

    R338 (2026-09-29). code-critic proposed « on add/delete/rename only »; `make
    select-audit` measured otherwise: these tests READ the content of every tracked file,
    and they were 69 of its 78 misses on plain edits. Three tests, ~10 s together."""
    if not any_change:
        return set()
    hits = set()
    for mod, path in known.items():
        if mod in all_tests:
            try:
                if _LISTS_THE_REPOSITORY.search(path.read_text(encoding="utf-8", errors="replace")):
                    hits.add(mod)
            except OSError:
                hits.add(mod)
    return hits


# T702 — the four crossroads. Every tool imports them for one helper, so a change to any of them
# reached 110-135 of the 213 test files, test_fleet_apply's 254 s among them, and none of them is
# `parc`: such a diff runs the selection alone, and the 150 % of `devtime_report --lever selected`
# was largely this. Reading WHICH names a file takes from them is a dependency table: built here
# from the sources at selection time, so it cannot go stale, and checked against a measure of what
# the tests really execute (`test_select_tests_symbols.py`). Any doubt gives the whole closure back.
CROSSROADS = ("tools/hud/hud.py", "tools/dev/gate_timer.py", "tools/dev/blast_radius.py",
              "tools/governance/config.py")
_REFLECTS = {"globals", "locals", "vars", "eval", "exec"}   # a name reached by its spelling


def _binds(stmt: ast.stmt) -> set[str] | None:
    """The names a top-level statement binds, or None when it is not a plain binding."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {stmt.name}
    if isinstance(stmt, ast.Assign) and all(isinstance(x, ast.Name) for x in stmt.targets):
        return {x.id for x in stmt.targets}
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return {stmt.target.id}
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return {(a.asname or a.name).split(".")[0] for a in stmt.names}
    return None


def _runs_as_a_script_only(stmt: ast.stmt) -> bool:
    """`if __name__ == "__main__":`, which no importer executes."""
    return (isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Compare)
            and getattr(stmt.test.left, "id", "") == "__name__"
            and any(getattr(c, "value", None) == "__main__" for c in stmt.test.comparators))


def changed_symbols(old: str, new: str) -> set[str] | None:
    """The top-level names whose definition differs, or None if anything else moved: an import,
    a statement that runs at import, a file that does not parse. Comments do not count."""
    def facts(source: str) -> tuple[dict[str, str], list[str]]:
        named: dict[str, str] = {}
        others: list[str] = []
        for s in ast.parse(source).body:
            binds = None if isinstance(s, (ast.Import, ast.ImportFrom)) else _binds(s)
            if binds is None:
                others.append(ast.dump(s))
                continue
            for b in binds:
                named[b] = named.get(b, "") + ast.dump(s)
        return named, others
    try:
        (was, was_other), (now, now_other) = facts(old), facts(new)
    except SyntaxError:
        return None
    if was_other != now_other:
        return None
    return {n for n in was.keys() | now.keys() if was.get(n) != now.get(n)}


def _refs(stmt: ast.AST) -> set[str]:
    """Every name a statement can reach: read, taken as a fixture (`def t(cfg)`), `alias.attr`,
    `alias.module.attr` (a module its importer holds, read through it: `names_through`)."""
    out: set[str] = set()
    for n in ast.walk(stmt):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            out.add(f"{n.value.id}.{n.attr}")
        elif (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Attribute)
              and isinstance(n.value.value, ast.Name)):
            out.add(f"{n.value.value.id}.{n.value.attr}.{n.attr}")
    return out


def _autouse(stmt: ast.stmt) -> bool:
    return any(k.arg == "autouse" for d in getattr(stmt, "decorator_list", ())
               if isinstance(d, ast.Call) for k in d.keywords)


def symbols_reached(tree: ast.Module, names: set[str]) -> set[str] | None:
    """`names` and everything in this file built on them, or None: the whole file is touched
    (a statement that runs at import reads them, an autouse fixture, a name reached by its
    spelling). A function that writes a `global` hands it on: its readers see what it wrote."""
    if any(isinstance(n, ast.Name) and n.id in _REFLECTS for n in ast.walk(tree)):
        return None
    reached = set(names)
    grew = True
    while grew:
        grew = False
        for stmt in tree.body:
            if _runs_as_a_script_only(stmt):
                continue
            binds = _binds(stmt)
            if not (_refs(stmt) | (binds or set())) & reached:
                continue
            if binds is None or _autouse(stmt):
                return None
            written = {g for n in ast.walk(stmt) if isinstance(n, ast.Global) for g in n.names}
            if not (binds | written) <= reached:
                reached |= binds | written
                grew = True
    return reached


def _says_nothing_of_a_module(tree: ast.Module) -> set[int]:
    """The ids of the `Name`s that read no attribute of what they hold: the optional import
    `try: import m / except ImportError: m = None`, then `if m is None:`. Read as handing the
    module around, these two lines of blast_radius made all of it, and all its importers, whole."""
    out = {id(n) for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    for n in ast.walk(tree):
        if (isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and len(n.ops) == 1
                and isinstance(n.ops[0], (ast.Is, ast.IsNot))
                and isinstance(n.comparators[0], ast.Constant) and n.comparators[0].value is None):
            out.add(id(n.left))
    return out


def _patches_another_name(tree: ast.Module, symbols: set[str]) -> set[int]:
    """The ids of `m` in `monkeypatch.setattr(m, "x", …)` with `x` no name of `symbols`: it writes
    one attribute, spelled, and reads none. A patched name that moved, or a computed one, says
    nothing of the kind and stays a module handed around. One such line made test_fleet_apply,
    a third of the suite, whole on every change to anything it imports."""
    return {id(n.args[0]) for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "setattr" and len(n.args) >= 2
            and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str)
            and n.args[1].value not in symbols}


def names_taken_from(tree: ast.Module, stem: str, symbols: set[str]) -> set[str] | None:
    """What this importer of module `stem` holds of `symbols`, spelled as it says them; None when
    it can reach all of it: `import *`, the module handed around as a value, or an edge with no
    `import` statement to read (a file loaded through importlib)."""
    aliases: set[str] = set()
    out: set[str] = set()
    found = False
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[-1] == stem:
                    found = True
                    if not a.asname and "." in a.name:
                        return None
                    aliases.add(a.asname or a.name)
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "").split(".")[-1] == stem:
                found = True
                for a in n.names:
                    if a.name == "*":
                        return None
                    if a.name in symbols:
                        out.add(a.asname or a.name)
            else:
                for a in n.names:
                    if a.name == stem:
                        found = True
                        aliases.add(a.asname or a.name)
    if not found:
        return None
    held = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    held |= _says_nothing_of_a_module(tree) | _patches_another_name(tree, symbols)
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in aliases and id(n) not in held:
            return None
        if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id in aliases and n.attr in symbols):
            out.add(f"{n.value.id}.{n.attr}")
    return out


def modules_held(tree: ast.Module, stem: str) -> set[str]:
    """The names this file binds to module `stem`, the attributes its own importers can read."""
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.asname or a.name for a in n.names if a.name.split(".")[-1] == stem}
        elif isinstance(n, ast.ImportFrom):
            out |= {a.asname or a.name for a in n.names if a.name == stem}
    return out


def names_through(tree: ast.Module, carrier: str, held: set[str],
                  symbols: set[str]) -> set[str] | None:
    """What this importer of `carrier` holds of `symbols` through a module `carrier` imports:
    `sl.hud.refresh` calls hud with no name of statusline changed, so the edge hud -> statusline
    says nothing of it (T702: `test_t622_hud_refresh…`, the one escape out of 2008 traced runs).
    Read by its spelling, whatever `sl` is: most tests load their module through importlib, with
    no `import` to name it. `sl.hud` read as a value (`setattr(sl.hud, …)`) can be any name of it.
    None: `from carrier import *`, or the module itself taken and handed around."""
    local: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[-1] == carrier:
            for a in n.names:
                if a.name == "*":
                    return None
                if a.name in held:
                    local.add(a.asname or a.name)
    parent = {id(n.value): n for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    quiet = _says_nothing_of_a_module(tree) | _patches_another_name(tree, symbols)
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in local and id(n) not in parent and id(n) not in quiet:
            return None
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            if n.value.id in local:
                if n.attr in symbols:
                    out.add(f"{n.value.id}.{n.attr}")
            elif n.attr in held:
                above = parent.get(id(n))
                if above is None:
                    if id(n) not in quiet:
                        out.add(f"{n.value.id}.{n.attr}")
                elif above.attr in symbols:
                    out.add(f"{n.value.id}.{n.attr}.{above.attr}")
    return out


def symbol_reach(imports: dict[str, set[str]], known: dict[str, Path],
                 changed: dict[str, set[str]]) -> dict[str, set[str] | None]:
    """{module: the names of it the change reaches, None for all of them}, across importers."""
    importers: dict[str, set[str]] = {}
    for mod, deps in imports.items():
        for d in deps:
            importers.setdefault(d, set()).add(mod)
    trees: dict[str, ast.Module | None] = {}

    def tree_of(mod: str) -> ast.Module | None:
        if mod not in trees:
            try:
                trees[mod] = ast.parse(known[mod].read_text(encoding="utf-8", errors="replace"))
            except (KeyError, OSError, SyntaxError):
                trees[mod] = None
        return trees[mod]

    reach: dict[str, set[str] | None] = {}
    todo: list[str] = []

    def hand(user: str, taken: set[str] | None) -> None:
        if taken is not None and not taken:
            return
        got = None if taken is None else symbols_reached(
            tree_of(user), taken | (reach.get(user) or set()))
        if user not in reach or got != reach[user]:
            reach[user] = got
            todo.append(user)

    for mod, names in changed.items():
        tree = tree_of(mod)
        reach[mod] = None if tree is None else symbols_reached(tree, names)
        todo.append(mod)
    while todo:
        mod = todo.pop()
        symbols = reach[mod]
        for user in importers.get(mod, ()):
            if user in reach and reach[user] is None:
                continue
            tree = tree_of(user)
            hand(user, None if symbols is None or tree is None else names_taken_from(
                tree, mod.rsplit(".", 1)[-1], symbols))
        for carrier in () if symbols is None else importers.get(mod, ()):
            tree = tree_of(carrier)
            held = modules_held(tree, mod.rsplit(".", 1)[-1]) if tree is not None else set()
            for user in importers.get(carrier, ()) if held else ():
                if user in reach and reach[user] is None:
                    continue
                tree = tree_of(user)
                hand(user, None if tree is None else names_through(
                    tree, carrier.rsplit(".", 1)[-1], held, symbols))
    return reach


def _test_names(tree: ast.Module, names: set[str]) -> set[str]:
    """The pytest node names among `names`: what `path::name` can say."""
    return {s.name for s in tree.body if getattr(s, "name", None) in names and (
        (isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) and s.name.startswith("test"))
        or (isinstance(s, ast.ClassDef) and s.name.startswith("Test")))}


def tests_of_statements(text: str, hit) -> set[str] | None:
    """The tests built on the top-level statements `hit` accepts, or None for the whole file: a
    sweep rule read a file, this reads which of its tests sweep (3 of test_fleet_apply's)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    start: set[str] = set()
    for stmt in tree.body:
        if hit(tree, stmt):
            binds = _binds(stmt)
            if binds is None:
                return None
            start |= binds
    reached = symbols_reached(tree, start) if start else None
    return (_test_names(tree, reached) or None) if reached else None


def _statement_text(text: str, stmt: ast.stmt) -> str:
    first = min([stmt.lineno, *(d.lineno for d in getattr(stmt, "decorator_list", ()))])
    return "\n".join(text.splitlines()[first - 1:stmt.end_lineno])


def crossroads_changed(sources: list[str], root: Path, roots: list[Path],
                       old_text) -> dict[str, set[str]]:
    """{module: the names its diff changed}, for the crossroads whose diff reads as symbols."""
    out: dict[str, set[str]] = {}
    if old_text is None:
        return out
    for c in sources:
        if c in CROSSROADS:
            old = old_text(c)
            try:
                new = (root / c).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            names = None if old is None else changed_symbols(old, new)
            if names is not None:
                out[module_name(root, root / c, roots)] = names
    return out


def select(root: Path, base: str | None = None, _max_depth: int | None = None,
           _sans_dossier: bool = False, _changed: list[str] | None = None,
           _old_text=None) -> dict:
    """Rend {'all': bool, 'tests': [...], 'reason': str}.

    `_max_depth` n'existe que pour `--self-test` : il bride la fermeture
    transitive afin de prouver que la brider fait bien rater un test. Voir R3.
    """
    # `_changed`: a fabricated diff, for the audit (`tools/dev/select_audit.py`) and tests.
    changed = changed_files(root, base) if _changed is None else list(_changed)
    if changed is None:
        pourquoi = _DERNIERE_PANNE_GIT or "cause inconnue"
        return {"all": True, "tests": [],
                "reason": f"impossible de lire le diff — {pourquoi}"}
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

    # L'etat genere par le harnais ne declenche pas la regle 2, mais reste
    # candidat a la mention litterale — cf. _EST_ETAT_GENERE.
    etat = [c for c in changed if _EST_ETAT_GENERE(c)]
    sources = [c for c in changed if not _EST_ETAT_GENERE(c)]

    non_py: list[str] = []
    for c in sources:
        n = Path(c).name
        if n in SUITE_CONFIG:
            return {"all": True, "tests": [], "reason": f"configuration de suite modifiée ({n})"}
        if n == "conftest.py":
            return {"all": True, "tests": [],
                    "reason": "conftest.py modifié — il s'applique sans être importé"}
        if not c.endswith(".py"):
            if _FORCE_LA_SUITE(c):
                return {"all": True, "tests": [],
                        "reason": f"fichier d'environnement modifié ({c}) — aucun test ne le nomme, tous en dépendent"}
            non_py.append(c)
    sources = [c for c in sources if c not in non_py]

    roots = source_roots(root)
    imports, dynamic, unparsable, known, dependency_only = _build_graph(root, roots)
    if unparsable:
        return {"all": True, "tests": [],
                "reason": f"{len(unparsable)} fichier(s) non parsable(s) — graphe incomplet : "
                          f"{', '.join(unparsable[:3])}"}

    # A module reached only through a `sys.path` insert is a dependency node, never a test
    # candidate: the walk prunes its directory for a reason (dot, `.gitignore`, R305).
    all_tests = sorted(m for m in imports if is_test(m.replace(".", "/") + ".py")
                       and m not in dependency_only)
    if not all_tests:
        return {"all": True, "tests": [],
                "reason": "aucun test trouvé — un sélecteur qui rend « rien » n'est pas distinguable d'un sélecteur cassé"}

    seeds: set[str] = set()
    hors_racine: list[str] = []
    for c in sources:
        mod = module_name(root, root / c, roots)
        if mod in imports:
            seeds.add(mod)
        elif _NOM_IMPORTABLE(mod):
            # Règle 6 — le fichier EST importable et le graphe ne le connaît pas :
            # on ne peut rien conclure sur ses importateurs.
            return {"all": True, "tests": [],
                    "reason": f"{c} ne se résout en aucun module connu — importateurs introuvables"}
        else:
            # Aucun `import` ne peut le nommer : son chemin traverse un dossier
            # dont le nom n'est pas un identifiant Python (`.claude/…`) et que
            # rien ne déclare comme racine. Il n'est atteignable que par
            # `subprocess` ou après une insertion dans `sys.path`. Le premier est
            # couvert par la mention littérale. Le second l'est par le graphe quand
            # l'insertion se résout : le dossier inséré est alors parcouru
            # (`_build_graph`), le fichier y est un module connu et n'arrive pas
            # ici. Une insertion qui ne se résout pas laisse son fichier `dynamic`,
            # donc toujours pris.
            hors_racine.append(c)

    # A data file (template, fixture, CSS) is read by the modules BESIDE it: their
    # importers are the tests that can see it change.
    for c in non_py:
        d = (root / c).parent
        seeds |= {m for m, p in known.items() if p.parent == d and not is_test(
            str(p.relative_to(root)).replace("\\", "/"))}
    # …and by the modules that NAME it, wherever they live (R338: the guide screenshots
    # and the model's JSON are read by views that name them from another folder —
    # `make select-audit` saw the render tests read them unselected). The basename only:
    # a folder name is too common a word to mean « reads this file ».
    for c in non_py:
        base_name = Path(c).name
        if len(base_name) < 8:
            continue
        for m, p in known.items():
            rel = str(p.relative_to(root)).replace("\\", "/")
            if is_test(rel):
                continue
            try:
                if base_name in p.read_text(encoding="utf-8", errors="replace"):
                    seeds.add(m)
            except OSError:
                continue

    # A crossroads read by symbol leaves the seeds; a reached `conftest` applies without being
    # imported, so it says nothing of who sees it: the plain closure then.
    if _old_text is None and _changed is None:
        start = base or _unpushed_base(root)
        if start:
            def _old_text(rel: str) -> str | None:
                return _git(root, "show", f"{start}:{rel}")
    by_symbol: dict[str, set[str] | None] = {}
    bysym = crossroads_changed(sources, root, roots, _old_text) if _max_depth is None else {}
    if bysym:
        by_symbol = symbol_reach(imports, known, bysym)
        if any(m.rsplit(".", 1)[-1] == "conftest" for m in by_symbol):
            bysym, by_symbol = {}, {}

    if _max_depth is None:
        reached = importers_closure(imports, seeds - set(bysym))
    else:  # chemin de mutation, --self-test uniquement
        reached, frontier = set(seeds), set(seeds)
        reverse: dict[str, set[str]] = {}
        for mod, deps in imports.items():
            for d in deps:
                reverse.setdefault(d, set()).add(mod)
        for _ in range(_max_depth):
            frontier = {u for f in frontier for u in reverse.get(f, ())} - reached
            reached |= frontier

    reached |= {m for m, names in by_symbol.items() if names is None}
    picked = {t for t in all_tests if t in reached}
    picked |= {t for t in all_tests if t in dynamic}   # import dynamique : toujours
    picked |= {t for t in all_tests if t in seeds}     # le test lui-même a changé
    named = tests_mentioning(root, sources + non_py + etat, set(all_tests), known) - picked
    picked |= named                                    # appel par subprocess
    # `narrow`: a test FILE some rule read at function level. A rule that wants the file wins.
    narrow: dict[str, set[str]] = {}
    for mod, names in by_symbol.items():
        if mod in picked or not names or mod not in known or mod not in set(all_tests):
            continue
        try:
            tests = _test_names(ast.parse(known[mod].read_text(encoding="utf-8",
                                                               errors="replace")), names)
        except (OSError, SyntaxError):
            picked.add(mod)
            continue
        if tests:
            narrow[mod] = tests
    par_dossier = set() if _sans_dossier else (
        tests_reading_the_directory(non_py, set(all_tests), known) - picked)
    picked |= par_dossier                              # glob du dossier, sans le nom
    for mod in par_dossier:
        narrow.pop(mod, None)
    meta = set() if _sans_dossier else (
        tests_scanning_the_test_files(sources, set(all_tests), known) - picked)
    picked |= meta                                     # gardes qui balaient tests/
    for mod in meta:
        narrow.pop(mod, None)
    # `_sans_dossier` (self-test) cuts the WHOLE directory family: containment (R338) now
    # covers what the two older rules caught, and a mutation must still be seen to miss.
    tree = set() if _sans_dossier else (
        tests_scanning_the_tree(sources + non_py, set(all_tests), known, root) - picked)
    listing = tests_listing_the_repository(bool(changed), set(all_tests), known) - picked
    swept = sources + non_py
    for mod in tree | listing:
        text = known[mod].read_text(encoding="utf-8", errors="replace")
        rel = known[mod].relative_to(root).as_posix()
        tests = tests_of_statements(text, lambda whole, stmt: (
            (mod in tree and any(_walk_matches(d, pat, rec, c)
                                 for d, pat, rec in _walks_in(whole, stmt, rel) for c in swept))
            or (mod in listing and bool(_LISTS_THE_REPOSITORY.search(_statement_text(text, stmt))))))
        if tests is None:
            picked.add(mod)            # gardes qui balaient un dossier, `git ls-files` (R338)
            narrow.pop(mod, None)
        else:
            narrow[mod] = narrow.get(mod, set()) | tests
    narrow = {m: v for m, v in narrow.items() if m not in picked}
    picked |= set(narrow)

    reason = f"{len(picked)}/{len(all_tests)} tests atteignent {len(seeds)} module(s) modifié(s)"
    if named:
        reason += f", dont {len(named)} par mention littérale (subprocess)"
    if hors_racine:
        reason += (f" ; {len(hors_racine)} fichier(s) hors racine d'imports "
                   f"({hors_racine[0]}…) — aucun import ne peut les atteindre")
    if non_py:
        reason += (f" ; {len(non_py)} fichier(s) non-Python sélectionné(s) par mention, "
                   f"dossier ou module voisin ({len(par_dossier)} par dossier)")
    if etat:
        reason += f" ; {len(etat)} fichier(s) d'état généré ignoré(s) comme déclencheur"
    if meta:
        reason += f" ; {len(meta)} garde(s) qui balaient tests/ (un test a changé)"
    if tree:
        reason += f" ; {len(tree)} garde(s) qui balaient un dossier modifié"
    if listing:
        reason += f" ; {len(listing)} test(s) qui lisent tout le dépôt (`git ls-files`)"
    if bysym:
        reason += f" ; {len(bysym)} carrefour(s) lu(s) par symbole"
    if narrow:
        reason += f" ; {len(narrow)} fichier(s) réduit(s) à leurs fonctions"
    return {"all": False, "tests": sorted(picked), "narrow": narrow,
            "paths": _chemins(root, sorted(picked), known, narrow), "reason": reason}


def _chemins(root: Path, tests: list[str], known: dict[str, Path],
             narrow: dict[str, set[str]] | None = None) -> list[str]:
    """Les chemins RÉELS des tests choisis.

    `as_paths` reconstruit un chemin en remplaçant les points par des slashs.
    C'était juste tant que tout module vivait sous la racine du dépôt ; ça cesse
    de l'être dès qu'une racine d'imports est déclarée — `check_prod_sync` sous
    `.claude/hooks/` deviendrait `sensor.py` à la racine, un chemin que pytest ne trouve
    pas. On rend donc le chemin que le parcours a réellement vu.
    """
    out = []
    for t in tests:
        p = known.get(t)
        path = (str(p.relative_to(root)).replace("\\", "/") if p
                else t.replace(".", "/") + ".py")
        out += [f"{path}::{n}" for n in sorted((narrow or {}).get(t, ()))] or [path]
    return out


def last_red_files(root: Path) -> list[str]:
    """The test files pytest's own cache says failed last, that still exist. [] when unreadable."""
    try:
        failed = json.loads((root / ".pytest_cache/v/cache/lastfailed").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(failed, dict):
        return []
    return sorted({n.split("::")[0] for n in failed if (root / n.split("::")[0]).is_file()})


def reds_first(paths: list[str], reds: list[str]) -> list[str]:
    """T700: the files red in the last run lead, so a push still red says so in its first seconds. Here
    because this script is the piece of the gate a repo receives again (a posed Makefile never is,
    REQ-PARC-78), and `--ff` through the environment breaks a nested `-p no:cacheprovider` (rc 4)."""
    red = set(reds)
    return sorted(paths, key=lambda p: p.split("::")[0] not in red)


def as_paths(tests: list[str]) -> list[str]:
    """Repli historique : ne vaut que pour les modules sous la racine du dépôt.

    Préférer `select()["paths"]`, qui rend le chemin observé. Conservé parce que
    des appelants externes s'en servent encore.
    """
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

        # L'angle mort `subprocess`. Le test n'importe RIEN : le graphe d'imports
        # le rate par construction, et c'est bien ce qu'on veut prouver — la
        # cellule serait ROUGE sans la règle de mention littérale. La seconde
        # assertion est ce qui empêche la règle d'être « tout prendre » déguisé.
        sp_root = Path(tempfile.mkdtemp(prefix="select-tests-subprocess-"))
        (sp_root / "toolbox").mkdir()
        (sp_root / "tests").mkdir()
        (sp_root / "toolbox" / "runner.py").write_text("N = 1\n")
        (sp_root / "tests" / "test_cli.py").write_text(
            "import subprocess, sys\n"
            "def test_cli():\n"
            "    subprocess.run([sys.executable, 'toolbox/runner.py'], check=True)\n")
        (sp_root / "tests" / "test_none.py").write_text("def test_w(): assert True\n")
        subprocess.run(["git", "init", "-q", str(sp_root)], check=True)
        subprocess.run(["git", "-C", str(sp_root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(sp_root), "-c", "user.email=t@t",
                        "-c", "user.name=t", "commit", "-qm", "base"], check=True)
        (sp_root / "toolbox" / "runner.py").write_text("N = 2\n")
        spsel = select(sp_root)
        cas_sp = [
            ("VERT   subprocess : le test qui NOMME le script sans l'importer est pris",
             not spsel["all"] and "tests.test_cli" in spsel["tests"]),
            ("VERT   ... et celui qui ne le nomme pas ne l'est pas",
             "tests.test_none" not in spsel["tests"]),
        ]
        shutil.rmtree(sp_root, ignore_errors=True)

        # Le dépôt dont TOUT le Python vit sous `.claude/` — n8n, mesuré le
        # 2026-08-03. Les deux causes y étaient indépendantes et suffisantes :
        # le `.py` hors racine tombait sur la règle 6, et l'état généré suivi par
        # git tombait sur la règle 2. Verdict avant correctif : SUITE ENTIÈRE à
        # chaque appel, quoi qu'on touche. La cellule qui compte est la SECONDE
        # de chaque paire — sans elle, « tout renvoyer » passerait pour un succès.
        cl_root = Path(tempfile.mkdtemp(prefix="select-tests-claude-"))
        (cl_root / ".claude" / "hooks").mkdir(parents=True)
        (cl_root / ".claude" / "curator").mkdir(parents=True)
        (cl_root / "tests").mkdir()
        (cl_root / ".claude" / "hooks" / "sensor.py").write_text("X = 1\n")
        (cl_root / ".claude" / "curator" / "usage.json").write_text("{}\n")
        (cl_root / "tests" / "test_hook.py").write_text(
            "import subprocess, sys\n"
            "def test_h():\n"
            "    subprocess.run([sys.executable, '.claude/hooks/sensor.py'], check=True)\n")
        (cl_root / "tests" / "test_neutre.py").write_text("def test_n(): assert True\n")
        subprocess.run(["git", "init", "-q", str(cl_root)], check=True)
        subprocess.run(["git", "-C", str(cl_root), "add", "-A", "-f"], check=True)
        subprocess.run(["git", "-C", str(cl_root), "-c", "user.email=t@t",
                        "-c", "user.name=t", "commit", "-qm", "base"], check=True)

        (cl_root / ".claude" / "hooks" / "sensor.py").write_text("X = 2\n")
        s_hook = select(cl_root)
        (cl_root / ".claude" / "hooks" / "sensor.py").write_text("X = 1\n")
        (cl_root / ".claude" / "curator" / "usage.json").write_text('{"n": 1}\n')
        s_etat = select(cl_root)
        cas_claude = [
            ("VERT   .claude/ : un hook modifié ne rend plus la suite entière",
             not s_hook["all"]),
            ("VERT   ... le test qui le lance par subprocess est pris",
             "tests.test_hook" in s_hook["tests"]),
            ("ROUGE  ... et le test sans rapport ne l'est PAS (sinon c'est « tout » déguisé)",
             "tests.test_neutre" not in s_hook["tests"]),
            ("VERT   état généré suivi par git : ne force plus la suite entière",
             not s_etat["all"]),
            ("ROUGE  ... et n'entraîne aucun test sans rapport",
             "tests.test_neutre" not in s_etat["tests"]),
        ]
        shutil.rmtree(cl_root, ignore_errors=True)

        # La racine DÉCLARÉE. Quand le dépôt dit lui-même qu'il importe depuis
        # `.claude/hooks`, le sous-arbre entre dans le graphe et la sélection
        # redevient une vraie sélection — pas un repli. Le test qui insère dans
        # `sys.path` un chemin ILLISIBLE est pris quoi qu'il arrive : après une
        # insertion, `import x` peut désigner n'importe quoi. Celui dont le dossier
        # inséré se lit dans la source n'est pris que si ce qu'il importe a changé.
        dc_root = Path(tempfile.mkdtemp(prefix="select-tests-declare-"))
        (dc_root / ".claude" / "hooks").mkdir(parents=True)
        (dc_root / "tests").mkdir()
        (dc_root / "outils").mkdir()
        (dc_root / ".claude" / "hooks" / "sensor.py").write_text("X = 1\n")
        (dc_root / "outils" / "zq_outil_cible.py").write_text("Y = 1\n")
        (dc_root / "conftest.py").write_text(
            "import sys\nsys.path.insert(0, '.claude/hooks')\n")
        (dc_root / "tests" / "test_imp.py").write_text(
            "import sensor\ndef test_i(): assert sensor.X\n")
        (dc_root / "tests" / "test_syspath.py").write_text(
            "import sys\nsys.path.insert(0, 'ailleurs')\ndef test_s(): assert True\n")
        (dc_root / "tests" / "test_insere.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'outils'))\n"
            "import zq_outil_cible\ndef test_o(): assert zq_outil_cible.Y\n")
        (dc_root / "tests" / "test_neutre.py").write_text("def test_n(): assert True\n")
        subprocess.run(["git", "init", "-q", str(dc_root)], check=True)
        subprocess.run(["git", "-C", str(dc_root), "add", "-A", "-f"], check=True)
        subprocess.run(["git", "-C", str(dc_root), "-c", "user.email=t@t",
                        "-c", "user.name=t", "commit", "-qm", "base"], check=True)
        (dc_root / ".claude" / "hooks" / "sensor.py").write_text("X = 2\n")
        s_decl = select(dc_root)
        (dc_root / ".claude" / "hooks" / "sensor.py").write_text("X = 1\n")
        (dc_root / "outils" / "zq_outil_cible.py").write_text("Y = 2\n")
        s_ins = select(dc_root)
        cas_decl = [
            ("VERT   racine déclarée : le test qui IMPORTE le hook est atteint par le graphe",
             not s_decl["all"] and "tests.test_imp" in s_decl["tests"]),
            ("VERT   ... le test qui insère un chemin illisible ('ailleurs') est toujours pris",
             "tests.test_syspath" in s_decl["tests"]),
            ("ROUGE  ... le test qui insère un dossier LISIBLE n'est pas pris pour un autre fichier",
             "tests.test_insere" not in s_decl["tests"]),
            ("ROUGE  ... et le test sans rapport ne l'est pas",
             "tests.test_neutre" not in s_decl["tests"]),
            ("VERT   ... et le chemin rendu est celui du disque, pas un nom pointé",
             "tests/test_imp.py" in s_decl["paths"]),
            ("VERT   dossier inséré lisible : le module importé À TRAVERS lui sélectionne le test",
             not s_ins["all"] and "tests.test_insere" in s_ins["tests"]),
        ]
        shutil.rmtree(dc_root, ignore_errors=True)

        full = select(root)
        crippled = select(root, _max_depth=1)

        cases = list(cas_src) + list(cas_sp) + list(cas_claude) + list(cas_decl) + [
            ("VERT   la fermeture complète attrape le test à 2 sauts",
             "tests.test_far" in full["tests"]),
            ("VERT   elle n'attrape PAS le test sans rapport",
             "tests.test_unrelated" not in full["tests"]),
            ("ROUGE  bridée à 1 saut, elle RATE le test à 2 sauts",
             "tests.test_far" not in crippled["tests"]),
        ]

        # Les sept sorties « tout renvoyer » doivent réellement se déclencher.
        (root / "uv.lock").write_text("x")
        cases.append(("VERT   un fichier d'environnement (uv.lock) force la suite entière",
                      select(root)["all"]))
        (root / "uv.lock").unlink()
        (root / "config").mkdir()
        (root / "config" / "config.yaml").write_text("a: 1\n")
        cases.append(("VERT   un fichier sous config/ force la suite entière", select(root)["all"]))
        shutil.rmtree(root / "config")

        # Règle 2 depuis le 2026-09-25 : un non-Python ordinaire SÉLECTIONNE au lieu de
        # tout rendre. Trois chemins, chacun avec la cellule qui prouve qu'il porte :
        # le test qui GLOBE le dossier sans nommer le fichier, le module VOISIN d'un
        # fichier de données, et le test sans rapport qui doit rester dehors.
        subprocess.run(["git", "-C", str(root), "checkout", "-q", "--", "."], check=True)
        (root / "notes").mkdir()
        (root / "notes" / "a.md").write_text("x\n")
        (root / "tests" / "test_glob.py").write_text(
            "from pathlib import Path\n"
            "def test_g(): assert list(Path('notes').glob('*.md'))\n")
        (root / "pkg" / "template.html").write_text("<p/>\n")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "docs"], check=True)
        (root / "notes" / "a.md").write_text("y\n")
        s_doc = select(root)
        s_doc_mute = select(root, _sans_dossier=True)
        (root / "notes" / "a.md").write_text("x\n")
        (root / "pkg" / "template.html").write_text("<p>2</p>\n")
        s_tpl = select(root)
        cases += [
            ("VERT   un .md ordinaire ne force plus la suite entière", not s_doc["all"]),
            ("VERT   ... le test qui globe son DOSSIER sans le nommer est pris",
             "tests.test_glob" in s_doc["tests"]),
            ("ROUGE  ... sans la règle du dossier, il est RATÉ (la règle porte)",
             "tests.test_glob" not in s_doc_mute["tests"]),
            ("ROUGE  ... et le test sans rapport ne l'est pas",
             "tests.test_unrelated" not in s_doc["tests"]),
            ("VERT   un fichier de données sélectionne les importateurs de ses modules VOISINS",
             not s_tpl["all"] and "tests.test_far" in s_tpl["tests"]),
            ("ROUGE  ... et pas le test sans rapport",
             "tests.test_unrelated" not in s_tpl["tests"]),
        ]
        (root / "pkg" / "template.html").write_text("<p/>\n")

        # A meta-guard walks every test file: a changed TEST must select it, and a
        # changed source module must not drag it in.
        (root / "tests" / "test_meta.py").write_text(
            "from pathlib import Path\n"
            "def test_m(): assert list(Path(__file__).parent.glob('test_*.py'))\n")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "meta"], check=True)
        (root / "tests" / "test_unrelated.py").write_text("def test_y(): assert 1\n")
        s_meta = select(root)
        s_meta_mute = select(root, _sans_dossier=True)
        subprocess.run(["git", "-C", str(root), "checkout", "-q", "--", "."], check=True)
        cases += [
            ("VERT   un test modifié sélectionne les gardes qui balaient tests/",
             "tests.test_meta" in s_meta["tests"]),
            ("ROUGE  ... sans la règle, le garde est RATÉ (la règle porte)",
             "tests.test_meta" not in s_meta_mute["tests"]),
        ]

        (root / "conftest.py").write_text("")
        cases.append(("VERT   un conftest.py force la suite entière", select(root)["all"]))
        (root / "conftest.py").unlink()

        (root / "pkg" / "broken.py").write_text("def (:\n")
        cases.append(("VERT   un fichier non parsable force la suite entière", select(root)["all"]))
        (root / "pkg" / "broken.py").unlink()

        # Règle 6 : un `.py` au nom IMPORTABLE que le graphe ne connaît pas
        # (ici sous un dossier élagué) doit forcer la suite entière — on ne peut
        # pas remonter ses importateurs, et un paquet-espace-de-noms rend
        # `build.gen.x` parfaitement atteignable par un `import`.
        (root / "build" / "gen").mkdir(parents=True)
        (root / "build" / "gen" / "x.py").write_text("X = 1\n")
        cases.append(("VERT   un .py au nom importable, inconnu du graphe, force la suite entière",
                      select(root)["all"]))
        shutil.rmtree(root / "build")

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
    chemins = r.get("paths") or as_paths(r["tests"])
    if args.dry:
        verdict = "SUITE ENTIÈRE" if r["all"] else f"{len(r['tests'])} test(s)"
        print(f"{verdict} — {r['reason']}")
        for t in chemins:
            print(f"  {t}")
        return 0
    if r["all"]:
        # No reds in front of it: `pytest tests/z.py tests/` collects a, then z (measured, pytest 9), the
        # directory's own order wins. Whole suite, so only the stop after 5 failures speeds a red here.
        print("tests/", file=sys.stdout)
    else:
        for t in reds_first(chemins, last_red_files(args.root.resolve())):
            print(t)
    print(f"# {r['reason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
