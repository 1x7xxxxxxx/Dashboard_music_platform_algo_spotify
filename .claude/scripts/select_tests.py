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
- un test qui **manipule `sys.path`** est toujours inclus, pour la même raison :
  après une insertion de chemin, `import x` peut désigner n'importe quoi ;
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
    return (n in _ENV_NAMES or n.startswith(("requirements", ".env"))
            or c.endswith(".sql") or c.startswith("config/"))
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
        dirnames[:] = [d for d in dirnames if d not in PRUNE and d != ".git"]
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


PRUNE = {".git", ".venv", "venv", "env", "node_modules", "__pycache__",
         "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache",
         "site-packages", ".tox", "htmlcov", ".idea", ".vscode"}


def _walk_python(root: Path, roots: list[Path] | None = None) -> list[Path]:
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
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        gardes = []
        for d in dirnames:
            if d in PRUNE:
                continue
            chemin = str(Path(dirpath) / d)
            if d.startswith(".") and not any(
                    a == chemin or a.startswith(chemin + os.sep) for a in autorises):
                continue
            gardes.append(d)
        dirnames[:] = gardes
        for f in filenames:
            if f.endswith(".py"):
                out.append(Path(dirpath) / f)
    return out


def build_graph(root: Path,
                roots: list[Path] | None = None,
                ) -> tuple[dict[str, set[str]], set[str], list[str], dict[str, Path]]:
    """(module -> modules importés), modules dynamiques, non parsables, module -> chemin.

    `roots` est passé par l'appelant pour n'être calculé qu'UNE fois : sa
    découverte parcourt l'arbre à la recherche des `conftest.py`, et un parcours
    de plus coûte ici plus cher que tout le reste (F4 — un `stat` sur `/mnt/c`).
    """
    roots = roots or source_roots(root)
    py = _walk_python(root, roots)
    known = {module_name(root, p, roots): p for p in py}
    # Un fichier, plusieurs noms possibles selon la racine par laquelle on l'importe.
    # `known` reste la carte CANONIQUE (un nom, celui du graphe) ; cet index-ci relie
    # chaque alias à ce nom canonique, et c'est lui qui résout les `import`.
    alias: dict[str, str] = {}
    for p in py:
        canon = module_name(root, p, roots)
        for a in module_aliases(root, p, roots):
            alias.setdefault(a, canon)
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
            # `sys.path` manipulé : après une insertion de chemin, `import x` peut
            # désigner un fichier qu'aucune arête statique ne relie à ce module.
            # C'est exactement la forme qu'ont les tests des scripts `.claude/`,
            # et c'est ce qui rend sûr de ne PAS rendre la suite entière quand un
            # `.py` hors racine bouge (règle 6).
            elif isinstance(node, ast.Attribute) and node.attr == "path" \
                    and isinstance(node.value, ast.Name) and node.value.id == "sys":
                dynamic.add(mod)
        if "importlib" in got:
            dynamic.add(mod)

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
        imports[mod] = resolved

    return imports, dynamic, unparsable, known


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
_TREE_SCAN_HINT = re.compile(r"\.rglob\(|\bos\.walk\(|glob\(\s*[\"']\*\*")
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
        if getattr(node.func, "id", "") == "Path" and node.args and \
                getattr(node.args[0], "id", "") == "__file__":
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


def scanned_directories(source: str, rel: str | None = None) -> set[str | None]:
    """Repo-relative directories whose `.py` files this test walks. Pure.

    `rel` is the test file's repo-relative path, which resolves `Path(__file__)` anchors.
    Empty set = the test walks no `.py` tree; `_UNKNOWN` (None) = the whole repository."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: dict[str, list[ast.AST]] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names.setdefault(t.id, []).append(n.value)
    loops = {n.target.id: n.iter for n in ast.walk(tree)
             if isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.target, ast.Name)}
    here = tuple(rel.split("/")) if rel else None
    out: set[str | None] = set()
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        pattern = (n.args[0].value if n.args and isinstance(n.args[0], ast.Constant)
                   and isinstance(n.args[0].value, str) else "")
        if n.func.attr == "rglob" and pattern.endswith(".py"):
            out |= _literal_paths(n.func.value, names, loops, here)
        elif n.func.attr == "glob" and pattern.startswith("**") and pattern.endswith(".py"):
            out |= _literal_paths(n.func.value, names, loops, here)
        elif n.func.attr == "walk" and getattr(n.func.value, "id", "") == "os" and n.args:
            out |= _literal_paths(n.args[0], names, loops, here)
    return out


def tests_scanning_the_tree(changed: list[str], all_tests: set[str],
                            known: dict[str, Path], root: Path | None = None) -> set[str]:
    """Tests that walk a `.py` tree containing a changed `.py` file."""
    changed_py = [c for c in changed if c.endswith(".py")]
    if not changed_py:
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
        dirs = scanned_directories(text, rel)
        if any(d is _UNKNOWN or d == "" or c == d or c.startswith(d + "/")
               for d in dirs for c in changed_py):
            hits.add(mod)
    return hits


def select(root: Path, base: str | None = None, _max_depth: int | None = None,
           _sans_dossier: bool = False) -> dict:
    """Rend {'all': bool, 'tests': [...], 'reason': str}.

    `_max_depth` n'existe que pour `--self-test` : il bride la fermeture
    transitive afin de prouver que la brider fait bien rater un test. Voir R3.
    """
    changed = changed_files(root, base)
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
    imports, dynamic, unparsable, known = build_graph(root, roots)
    if unparsable:
        return {"all": True, "tests": [],
                "reason": f"{len(unparsable)} fichier(s) non parsable(s) — graphe incomplet : "
                          f"{', '.join(unparsable[:3])}"}

    all_tests = sorted(m for m in imports if is_test(m.replace(".", "/") + ".py"))
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
            # `subprocess` ou après une insertion dans `sys.path` — les deux sont
            # couverts, l'un par la mention littérale, l'autre par `dynamic`.
            hors_racine.append(c)

    # A data file (template, fixture, CSS) is read by the modules BESIDE it: their
    # importers are the tests that can see it change.
    for c in non_py:
        d = (root / c).parent
        seeds |= {m for m, p in known.items() if p.parent == d and not is_test(
            str(p.relative_to(root)).replace("\\", "/"))}

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
    named = tests_mentioning(root, sources + non_py + etat, set(all_tests), known) - picked
    picked |= named                                    # appel par subprocess
    par_dossier = set() if _sans_dossier else (
        tests_reading_the_directory(non_py, set(all_tests), known) - picked)
    picked |= par_dossier                              # glob du dossier, sans le nom
    meta = set() if _sans_dossier else (
        tests_scanning_the_test_files(sources, set(all_tests), known) - picked)
    picked |= meta                                     # gardes qui balaient tests/
    tree = tests_scanning_the_tree(sources, set(all_tests), known, root) - picked
    picked |= tree                                     # gardes qui balaient un arbre de .py

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
        reason += f" ; {len(tree)} garde(s) qui balaient un arbre de .py modifié"
    return {"all": False, "tests": sorted(picked),
            "paths": _chemins(root, sorted(picked), known), "reason": reason}


def _chemins(root: Path, tests: list[str], known: dict[str, Path]) -> list[str]:
    """Les chemins RÉELS des tests choisis.

    `as_paths` reconstruit un chemin en remplaçant les points par des slashs.
    C'était juste tant que tout module vivait sous la racine du dépôt ; ça cesse
    de l'être dès qu'une racine d'imports est déclarée — `observe` sous
    `.claude/hooks/` deviendrait `observe.py`, un chemin que pytest ne trouve
    pas. On rend donc le chemin que le parcours a réellement vu.
    """
    out = []
    for t in tests:
        p = known.get(t)
        out.append(str(p.relative_to(root)).replace("\\", "/") if p
                   else t.replace(".", "/") + ".py")
    return out


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
        (cl_root / ".claude" / "hooks" / "observe.py").write_text("X = 1\n")
        (cl_root / ".claude" / "curator" / "usage.json").write_text("{}\n")
        (cl_root / "tests" / "test_hook.py").write_text(
            "import subprocess, sys\n"
            "def test_h():\n"
            "    subprocess.run([sys.executable, '.claude/hooks/observe.py'], check=True)\n")
        (cl_root / "tests" / "test_neutre.py").write_text("def test_n(): assert True\n")
        subprocess.run(["git", "init", "-q", str(cl_root)], check=True)
        subprocess.run(["git", "-C", str(cl_root), "add", "-A", "-f"], check=True)
        subprocess.run(["git", "-C", str(cl_root), "-c", "user.email=t@t",
                        "-c", "user.name=t", "commit", "-qm", "base"], check=True)

        (cl_root / ".claude" / "hooks" / "observe.py").write_text("X = 2\n")
        s_hook = select(cl_root)
        (cl_root / ".claude" / "hooks" / "observe.py").write_text("X = 1\n")
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
        # redevient une vraie sélection — pas un repli. Et le test qui bricole
        # `sys.path` est pris quoi qu'il arrive : après une insertion, `import x`
        # peut désigner n'importe quoi.
        dc_root = Path(tempfile.mkdtemp(prefix="select-tests-declare-"))
        (dc_root / ".claude" / "hooks").mkdir(parents=True)
        (dc_root / "tests").mkdir()
        (dc_root / ".claude" / "hooks" / "observe.py").write_text("X = 1\n")
        (dc_root / "conftest.py").write_text(
            "import sys\nsys.path.insert(0, '.claude/hooks')\n")
        (dc_root / "tests" / "test_imp.py").write_text(
            "import observe\ndef test_i(): assert observe.X\n")
        (dc_root / "tests" / "test_syspath.py").write_text(
            "import sys\nsys.path.insert(0, 'ailleurs')\ndef test_s(): assert True\n")
        (dc_root / "tests" / "test_neutre.py").write_text("def test_n(): assert True\n")
        subprocess.run(["git", "init", "-q", str(dc_root)], check=True)
        subprocess.run(["git", "-C", str(dc_root), "add", "-A", "-f"], check=True)
        subprocess.run(["git", "-C", str(dc_root), "-c", "user.email=t@t",
                        "-c", "user.name=t", "commit", "-qm", "base"], check=True)
        (dc_root / ".claude" / "hooks" / "observe.py").write_text("X = 2\n")
        s_decl = select(dc_root)
        cas_decl = [
            ("VERT   racine déclarée : le test qui IMPORTE le hook est atteint par le graphe",
             not s_decl["all"] and "tests.test_imp" in s_decl["tests"]),
            ("VERT   ... le test qui manipule sys.path est toujours pris",
             "tests.test_syspath" in s_decl["tests"]),
            ("ROUGE  ... et le test sans rapport ne l'est pas",
             "tests.test_neutre" not in s_decl["tests"]),
            ("VERT   ... et le chemin rendu est celui du disque, pas un nom pointé",
             "tests/test_imp.py" in s_decl["paths"]),
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
        print("tests/", file=sys.stdout)
    else:
        for t in chemins:
            print(t)
    print(f"# {r['reason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
