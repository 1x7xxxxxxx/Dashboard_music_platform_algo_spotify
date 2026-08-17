#!/usr/bin/env python3
"""Rend rouge une CI qui dépense du temps sans acheter de garantie.

Pourquoi cet outil existe
-------------------------
Mesuré le 2026-08-17 sur les deux seuls dépôts de la flotte qui ont une CI
GitHub. Aucun des quatre défauts ci-dessous n'était visible dans un rapport :
tous les runs étaient VERTS, et c'est exactement ce qui les rendait invisibles.
Un test qui échoue se voit ; un run qui coûte le double ne se voit pas.

Ce que chaque contrôle a réellement attrapé, et ce qu'il a coûté :

`ci-runs-twice-for-one-commit`
    `streamlytics` déclarait `push: branches: ["**"]` ET `pull_request:`. Sur
    les 20 derniers runs : **15 SHA distincts pour 20 runs**, 5 commits ayant
    déclenché les deux événements. Sur une branche à PR ouverte c'est tous les
    commits, à 2 min 40 le run. Le second run ne peut rien apprendre que le
    premier n'ait déjà dit — même arbre, même commit, même résultat.

`ci-has-no-concurrency-group`
    Trois poussées en une minute mettaient trois runs complets en file, et les
    trois allaient au bout. Un seul peut encore être vrai. `msdr` avait le
    groupe depuis le début, `streamlytics` non — la flotte partage une config,
    pas ses workflows.

`gate-on-a-job-that-cannot-fail`
    `chaos-tests` porte `continue-on-error: true` — il ne peut PAS faire échouer
    le build — et portait `needs: pytest`. Faire attendre un job incapable de
    rapporter un échec derrière un job qui, lui, le peut, n'achète rien. Coût
    mesuré sur le run 29207436395 : `pytest` finit à 20:20:51, les deux jobs
    dépendants démarrent à 20:20:54 et finissent à 20:22:01 — 67 s de chemin
    critique ajoutés à un run de 3 min, sur chaque build vert.

`parallel-safe-fixtures-run-serially`
    Le plus cher, et le plus discret. `src/Application/tests/conftest.py` de
    `msdr` lit `PYTEST_XDIST_WORKER` depuis toujours pour nommer un schéma PG
    éphémère par worker — l'isolation parallèle était écrite, testée, payée. La
    CI lançait `pytest tests/ -q` sans `-n` : 2104 tests en un seul processus,
    132 s. Personne ne pouvait le voir en lisant l'un ou l'autre fichier ; il
    fallait les lire ENSEMBLE. C'est la forme même du défaut que ce garde
    existe pour attraper — une promesse tenue d'un côté et jamais appelée de
    l'autre.

Le mode de défaillance à éviter
-------------------------------
Un garde de CI qui devient rouge pour une raison stylistique se fait désarmer,
et emporte avec lui les trois contrôles qui comptaient. Chaque règle ci-dessous
ne se déclenche donc que sur un GASPILLAGE DÉMONTRABLE : du temps machine dépensé
qui ne peut, par construction, rien apprendre de neuf. Une CI lente parce que ses
tests sont lents n'est pas un hit — c'est un sujet, pas un défaut.

    python3 check_ci_waste.py              # depuis la racine du dépôt
    python3 check_ci_waste.py --root DIR
    python3 check_ci_waste.py --self-test  # R3 — vu rouge avant d'être cru
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Les listes de branches qui, combinées a un declencheur `pull_request`, font
# tourner le workflow deux fois pour un meme commit.
_JOKERS = {"**", "*", "**/*"}

# Un `pytest` invoque par la CI. On cherche l'appel, pas le mot : `pytest.ini`,
# une phrase de commentaire, et surtout `pip install pytest-xdist` ne sont pas
# des invocations. La premiere version omettait ce dernier cas et accusait deux
# jobs de `msdr` sur leur ligne d'INSTALLATION — un garde qui accuse a tort se
# fait desarmer, et emporte les regles qui comptaient.
_APPEL_PYTEST = re.compile(
    r"^\s*(?:uv\s+run\s+|poetry\s+run\s+|python[0-9.]*\s+-m\s+)?"
    r"pytest\b(?P<args>[^\n]*)$", re.MULTILINE)
_A_DES_WORKERS = re.compile(r"(?:^|\s)(?:-n\b|--numprocesses\b|--dist\b)")
# Les arguments qui ne sont pas des chemins de cible.
_PAS_UNE_CIBLE = re.compile(r"^-|^[A-Z_]+=")


def _charge_yaml():
    try:
        import yaml
    except ImportError:                                  # pragma: no cover
        return None
    return yaml


def _workflows(root: Path) -> list[Path]:
    d = root / ".github" / "workflows"
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir()
                  if p.suffix in (".yml", ".yaml") and p.is_file())


def _branches(bloc) -> list[str]:
    """Les branches d'un declencheur, quelle que soit la forme ecrite."""
    if not isinstance(bloc, dict):
        return []
    for cle in ("branches", "branches-ignore"):
        v = bloc.get(cle)
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v]
    return []


def _ligne_de(texte: str, motif: str) -> int:
    for i, ligne in enumerate(texte.splitlines(), 1):
        if motif in ligne:
            return i
    return 1


def _conftests_xdist(root: Path) -> list[Path]:
    """Les `conftest.py` qui ont ECRIT une isolation par worker xdist.

    On ne devine pas : on cherche la variable que xdist pose lui-meme,
    `PYTEST_XDIST_WORKER`. Un conftest qui la lit declare noir sur blanc qu'il
    sait tourner en parallele. C'est cette declaration, et elle seule, qui rend
    un `pytest` sans `-n` reprochable — sans elle, le serie est un choix.
    """
    out: list[Path] = []
    import os
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", ".venv", "venv", "node_modules",
                                    "__pycache__", ".tox", "build", "dist",
                                    "site-packages", ".pytest_cache"}]
        if "conftest.py" not in filenames:
            continue
        p = Path(dirpath) / "conftest.py"
        try:
            if "PYTEST_XDIST_WORKER" in p.read_text(encoding="utf-8", errors="replace"):
                out.append(p)
        except OSError:
            continue
    return out


def analyse(root: Path) -> list[tuple[str, int, str, str]]:
    """Rend [(chemin, ligne, classe, explication)] — vide si la CI ne gaspille rien."""
    yaml = _charge_yaml()
    if yaml is None:
        raise RuntimeError(
            "pyyaml absent : ce garde ne peut pas conclure. Il sort en erreur "
            "plutôt qu'en vert — un garde qui passe faute de dépendance rend "
            "exactement le vert qui ne veut rien dire.")

    hits: list[tuple[str, int, str, str]] = []
    fichiers = _workflows(root)
    xdist_prets = _conftests_xdist(root)

    for wf in fichiers:
        rel = str(wf.relative_to(root)).replace("\\", "/")
        try:
            texte = wf.read_text(encoding="utf-8", errors="replace")
            doc = yaml.safe_load(texte)
        except (OSError, Exception):                     # noqa: B014 — yaml.YAMLError inclus
            continue
        if not isinstance(doc, dict):
            continue

        # `on:` est lu par le parseur YAML 1.1 comme le booleen True.
        decl = doc.get("on", doc.get(True))
        if not isinstance(decl, dict):
            decl = {}

        push, pr = decl.get("push"), decl.get("pull_request")
        declenche_sur_evenement = ("push" in decl) or ("pull_request" in decl)

        # 1 — le meme commit paye deux runs complets.
        if push is not None and pr is not None:
            br = _branches(push)
            if not br or any(b in _JOKERS for b in br):
                large = "toutes les branches" if not br else ", ".join(br)
                hits.append((
                    rel, _ligne_de(texte, "push"), "ci-runs-twice-for-one-commit",
                    f"`push` couvre {large} et `pull_request` est déclaré : sur une "
                    f"branche à PR ouverte, chaque commit lance le workflow DEUX fois, "
                    f"même arbre et même résultat. Restreindre `push` aux branches "
                    f"d'intégration."))

        # 2 — les runs perimes ne sont pas annules.
        #
        # Uniquement sur les workflows d'ITERATION : ceux qui portent un
        # `pull_request`, ou un `push` couvrant des branches de travail. Un
        # workflow de release declenche par `push: [main]` a ete signale par la
        # premiere version — annuler une release a mi-chemin est une PERTE, pas
        # une economie. Un garde qui prescrit une regression n'est pas un garde.
        iteratif = pr is not None or any(b in _JOKERS for b in _branches(push))
        if declenche_sur_evenement and iteratif and not doc.get("concurrency"):
            hits.append((
                rel, 1, "ci-has-no-concurrency-group",
                "aucun bloc `concurrency:` : deux poussées rapprochées laissent "
                "tourner les deux runs jusqu'au bout alors qu'un seul peut encore "
                "être vrai. Ajouter `concurrency: {group: ..., cancel-in-progress: true}`."))

        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            continue

        for nom, job in jobs.items():
            if not isinstance(job, dict):
                continue

            # 3 — un job qui ne peut pas echouer attend un job qui le peut.
            if job.get("continue-on-error") is True and job.get("needs"):
                hits.append((
                    rel, _ligne_de(texte, f"{nom}:"), "gate-on-a-job-that-cannot-fail",
                    f"le job `{nom}` porte `continue-on-error: true` — il ne peut pas "
                    f"faire échouer le build — et attend `{job['needs']}`. Cette attente "
                    f"n'achète aucune garantie et allonge le chemin critique."))

            # 4 — l'isolation parallele est ecrite, et jamais appelee.
            #
            # Ne se declenche que sur l'invocation de la suite ENTIERE, celle
            # dont la cible est exactement le dossier qui porte le conftest
            # prepare pour xdist. La premiere version signalait aussi les jobs
            # qui lancent une sous-suite dediee (`tests/contract`, `tests/chaos`,
            # un fichier de DR en nocturne) : y ajouter des workers n'achete
            # rien, et le reproche etait faux. Un seul hit par job.
            if not xdist_prets:
                continue
            wd_job = ((job.get("defaults") or {}).get("run") or {}).get("working-directory")
            deja_vu = False
            for etape in job.get("steps") or []:
                if deja_vu or not isinstance(etape, dict):
                    continue
                run = etape.get("run")
                if not isinstance(run, str):
                    continue
                wd = etape.get("working-directory") or wd_job or "."
                for m in _APPEL_PYTEST.finditer(run):
                    args = m.group("args")
                    if _A_DES_WORKERS.search(args):
                        continue
                    cibles = [a for a in args.split() if not _PAS_UNE_CIBLE.match(a)]
                    resolues = {(root / wd / c).resolve() for c in cibles}
                    concerne = next((cf for cf in xdist_prets
                                     if cf.parent.resolve() in resolues), None)
                    if concerne is None:
                        continue
                    conf = str(concerne.relative_to(root)).replace("\\", "/")
                    hits.append((
                        rel, _ligne_de(texte, m.group(0).strip()[:40]),
                        "parallel-safe-fixtures-run-serially",
                        f"le job `{nom}` lance la suite entière sans `-n` alors que "
                        f"`{conf}` lit `PYTEST_XDIST_WORKER` : l'isolation par worker "
                        f"est écrite et payée, et la suite tourne en un seul processus."))
                    deja_vu = True
                    break
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    root = args.root.resolve()
    if not (root / ".github" / "workflows").is_dir():
        print("aucun workflow GitHub — rien à vérifier ici.", file=sys.stderr)
        return 0

    try:
        hits = analyse(root)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2

    # Les hits nus sur stdout, `chemin:ligne:classe: texte`. Le resume part sur
    # stderr : un prefixe decoratif devant le chemin casse tout appelant qui
    # decoupe sur `:` — c'est la lecon de `check_config_refs.py`.
    for rel, ligne, classe, quoi in hits:
        print(f"{rel}:{ligne}:{classe}: {quoi}")

    if hits:
        print(f"\n{len(hits)} gaspillage(s) de CI — du temps machine qui n'achète "
              f"aucune garantie.", file=sys.stderr)
        return 1
    print("CI : aucun gaspillage démontrable détecté.", file=sys.stderr)
    return 0


# ---------------------------------------------------------------- R3

def self_test() -> int:
    """Vu ROUGE sur chaque défaut, VERT une fois corrigé — et pas l'inverse.

    Chaque classe a DEUX cellules : une qui doit rougir, une qui doit rester
    verte. Sans la seconde, « tout signaler » passerait pour un succès.
    """
    import shutil
    import tempfile

    def ecrit(root: Path, nom: str, contenu: str) -> None:
        d = root / ".github" / "workflows"
        d.mkdir(parents=True, exist_ok=True)
        (d / nom).write_text(contenu, encoding="utf-8")

    def classes(root: Path) -> set[str]:
        return {c for _, _, c, _ in analyse(root)}

    cas: list[tuple[str, bool]] = []
    racine = Path(tempfile.mkdtemp(prefix="ci-waste-selftest-"))
    try:
        # --- 1. double run
        r = racine / "double"
        ecrit(r, "ci.yml",
              "name: CI\non:\n  push:\n    branches: ['**']\n  pull_request:\n"
              "    branches: [main]\nconcurrency:\n  group: g\n  cancel-in-progress: true\n"
              "jobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")
        cas.append(("ROUGE  push joker + pull_request → double run",
                    "ci-runs-twice-for-one-commit" in classes(r)))

        r2 = racine / "double-ok"
        ecrit(r2, "ci.yml",
              "name: CI\non:\n  push:\n    branches: [main]\n  pull_request:\n"
              "    branches: [main]\nconcurrency:\n  group: g\n  cancel-in-progress: true\n"
              "jobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")
        cas.append(("VERT   push restreint aux branches d'intégration → pas de hit",
                    "ci-runs-twice-for-one-commit" not in classes(r2)))

        # --- 2. concurrency absente
        # Workflow d'ITERATION (il porte un `pull_request`) : c'est celui qu'on
        # relance sans cesse, donc celui pour qui l'annulation vaut quelque chose.
        r3 = racine / "conc"
        ecrit(r3, "ci.yml",
              "name: CI\non:\n  push:\n    branches: [main]\n  pull_request:\n"
              "    branches: [main]\njobs:\n  t:\n"
              "    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")
        cas.append(("ROUGE  aucun bloc concurrency sur un workflow d'itération",
                    "ci-has-no-concurrency-group" in classes(r3)))
        cas.append(("VERT   ... et le workflow qui en a un n'est pas signalé",
                    "ci-has-no-concurrency-group" not in classes(r2)))

        # --- 3. garde derriere un job qui ne peut pas echouer
        r4 = racine / "gate"
        ecrit(r4, "ci.yml",
              "name: CI\non:\n  push:\n    branches: [main]\nconcurrency:\n  group: g\n"
              "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo a\n"
              "  b:\n    runs-on: ubuntu-latest\n    needs: a\n    continue-on-error: true\n"
              "    steps:\n      - run: echo b\n")
        cas.append(("ROUGE  continue-on-error + needs → attente qui n'achète rien",
                    "gate-on-a-job-that-cannot-fail" in classes(r4)))

        r5 = racine / "gate-ok"
        ecrit(r5, "ci.yml",
              "name: CI\non:\n  push:\n    branches: [main]\nconcurrency:\n  group: g\n"
              "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo a\n"
              "  b:\n    runs-on: ubuntu-latest\n    needs: a\n"
              "    steps:\n      - run: echo b\n")
        cas.append(("VERT   ... un `needs` sur un job qui PEUT échouer reste légitime",
                    "gate-on-a-job-that-cannot-fail" not in classes(r5)))

        # --- 4. isolation xdist ecrite, jamais appelee
        r6 = racine / "xdist"
        (r6 / "tests").mkdir(parents=True)
        (r6 / "tests" / "conftest.py").write_text(
            "import os\n_W = os.environ.get('PYTEST_XDIST_WORKER', 'main')\n", encoding="utf-8")
        ecrit(r6, "ci.yml",
              "name: CI\non:\n  push:\n    branches: [main]\nconcurrency:\n  group: g\n"
              "jobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
              "      - run: uv run pytest tests/ -q\n")
        cas.append(("ROUGE  conftest prêt pour xdist, pytest lancé sans -n",
                    "parallel-safe-fixtures-run-serially" in classes(r6)))

        r7 = racine / "xdist-ok"
        (r7 / "tests").mkdir(parents=True)
        (r7 / "tests" / "conftest.py").write_text(
            "import os\n_W = os.environ.get('PYTEST_XDIST_WORKER', 'main')\n", encoding="utf-8")
        ecrit(r7, "ci.yml",
              "name: CI\non:\n  push:\n    branches: [main]\nconcurrency:\n  group: g\n"
              "jobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
              "      - run: uv run pytest tests/ -q -n auto\n")
        cas.append(("VERT   ... et `-n auto` éteint le hit",
                    "parallel-safe-fixtures-run-serially" not in classes(r7)))

        # La cellule qui empeche la regle 4 d'etre « tout signaler » deguise :
        # sans conftest xdist, un pytest en serie est un CHOIX, pas un defaut.
        r8 = racine / "xdist-absent"
        (r8 / "tests").mkdir(parents=True)
        (r8 / "tests" / "conftest.py").write_text("import os\n", encoding="utf-8")
        ecrit(r8, "ci.yml",
              "name: CI\non:\n  push:\n    branches: [main]\nconcurrency:\n  group: g\n"
              "jobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
              "      - run: uv run pytest tests/ -q\n")
        cas.append(("VERT   ... et sans conftest xdist, la série n'est pas un défaut",
                    "parallel-safe-fixtures-run-serially" not in classes(r8)))

        # --- Les trois faux positifs mesures le 2026-08-17 sur la flotte, chacun
        # avec la cellule qui l'aurait attrape. Ils viennent tous du meme geste :
        # une regle assez large pour avoir raison souvent, et tort quelque part.

        # a) `pip install pytest-xdist` n'est pas une invocation de pytest.
        #    Signale sur `msdr` (dr-nightly, ml-nightly) sur leur ligne d'INSTALL.
        r10 = racine / "pipinstall"
        (r10 / "tests").mkdir(parents=True)
        (r10 / "tests" / "conftest.py").write_text(
            "import os\n_W = os.environ.get('PYTEST_XDIST_WORKER', 'main')\n", encoding="utf-8")
        ecrit(r10, "ci.yml",
              "name: CI\non:\n  push:\n    branches: [main]\nconcurrency:\n  group: g\n"
              "jobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
              "      - run: |\n          pip install -r requirements.txt\n"
              "          pip install pytest-xdist pytest-cov\n")
        cas.append(("VERT   `pip install pytest-xdist` n'est pas une invocation de pytest",
                    "parallel-safe-fixtures-run-serially" not in classes(r10)))

        # b) une SOUS-suite dediee lancee en serie n'est pas un gaspillage.
        #    Signale sur `contract-tests`, `chaos-tests` et un fichier de DR.
        r11 = racine / "sous-suite"
        (r11 / "tests" / "contract").mkdir(parents=True)
        (r11 / "tests" / "conftest.py").write_text(
            "import os\n_W = os.environ.get('PYTEST_XDIST_WORKER', 'main')\n", encoding="utf-8")
        ecrit(r11, "ci.yml",
              "name: CI\non:\n  push:\n    branches: [main]\nconcurrency:\n  group: g\n"
              "jobs:\n  contract:\n    runs-on: ubuntu-latest\n    steps:\n"
              "      - run: uv run pytest tests/contract -v\n")
        cas.append(("VERT   une sous-suite dédiée en série n'est pas un défaut",
                    "parallel-safe-fixtures-run-serially" not in classes(r11)))

        # c) un workflow de RELEASE sur `push: [main]` ne doit pas se faire
        #    prescrire `cancel-in-progress` : annuler une release a mi-chemin
        #    est une perte. Signale sur `cd-release.yml` de streamlytics.
        r12 = racine / "release"
        ecrit(r12, "cd-release.yml",
              "name: Release\non:\n  push:\n    branches: [main]\n  workflow_dispatch:\n"
              "jobs:\n  ship:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ship\n")
        cas.append(("VERT   un workflow de release n'est pas sommé de s'auto-annuler",
                    "ci-has-no-concurrency-group" not in classes(r12)))
        cas.append(("ROUGE  ... mais un workflow d'itération sans groupe l'est toujours",
                    "ci-has-no-concurrency-group" in classes(r3)))

        # Un depot sans workflow ne peut pas gaspiller.
        r9 = racine / "vide"
        r9.mkdir(parents=True)
        cas.append(("VERT   un dépôt sans workflow ne rend aucun hit", not analyse(r9)))

        ok = True
        for label, passed in cas:
            print(f"  {'OK ' if passed else 'KO '} {label}")
            ok &= passed
    finally:
        shutil.rmtree(racine, ignore_errors=True)

    print()
    print("Un run vert qui coûte le double reste vert : c'est pour ça qu'il faut un garde."
          if ok else "ÉCHEC — ne pas livrer.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
