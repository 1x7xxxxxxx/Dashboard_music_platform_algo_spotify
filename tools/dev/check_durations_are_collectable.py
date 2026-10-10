#!/usr/bin/env python3
"""Chaque entrée de `.test_durations` désigne un test que pytest COLLECTE.

Type: Utility
Uses: json, subprocess, sys, pathlib
Triggers: .github/workflows/ci.yml
Persists in: nothing — lecture seule, sortie 0 ou 1

Pourquoi ce contrôle, et pourquoi PAS dans la suite
-----------------------------------------------------
`.test_durations` équilibre les six shards de CI. Une entrée qui ne désigne plus rien
gonfle la part d'un shard avec un temps qui ne sera jamais payé ; un test collecté sans
durée reçoit de `pytest-split` une durée MOYENNE — exactement ce que ce fichier existe
pour empêcher.

Mesuré le 2026-09-18 : **26 entrées non collectables pour 33,2 s**, dont deux à elles
seules pesaient **27,8 s (84 % de la masse)** — les deux contrôles de fraîcheur sortis de
la suite vers la CI le même jour. Et **40 tests collectés sans durée**.

⚠️ **Le prédicat ÉVIDENT rend 0.** « Le fichier du node-id existe-t-il sur disque ? » ne
trouve **aucun** des 26 : tous vivent dans des fichiers présents. Ce sont des tests
renommés, retirés, ou dont la paramétrisation a changé. La seule référence qui ne ment pas
est une COLLECTE réelle.

Ce contrôle vit en CI et non dans `make test` pour la raison que
`.claude/dev-docs/test-suite-performance.md` documente : une collecte coûte ~8 s, et ce
dépôt a déjà sorti de la suite les contrôles de fraîcheur pour ce motif exact. Le garde
`tests/test_the_shards_are_balanced_by_real_durations.py` reste dans la suite — il
surveille les FICHIERS, question moins chère et question différente.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DUR = _ROOT / ".test_durations"


def _base(node_id: str) -> str:
    """The test FUNCTION a node-id belongs to: the id without its `[param]`."""
    return node_id.split("[", 1)[0]


def inherited(sans, phantoms, durees, collectes) -> tuple[list[str], dict]:
    """R497 — what is left to judge once a parametrized id inherits from its function.

    A new `[param]` of a function that already has measured params (a catalogue class
    added to a test parametrized over the catalogue) is given by `pytest-split` the mean
    of its file, which is already measured: re-measuring it bought nothing and was the
    first refusal of the commit hook (`test-durations-missing`, 68 in 7 days). Likewise
    a phantom `[param]` whose function is still collected weighs one param of a known
    function. A function never measured, or a phantom whose function is gone, still
    fails. Pure: `--fix` still drops every phantom and measures what is returned."""
    mesurees = {_base(k) for k in durees if "[" in k}
    vivantes = {_base(k) for k in collectes}
    reste = [k for k in sans if "[" not in k or _base(k) not in mesurees]
    fantomes = {k: v for k, v in phantoms.items()
                if "[" not in k or _base(k) not in vivantes}
    return reste, fantomes


def load_durations() -> dict | None:
    """`.test_durations` parsed, or None with the remedy printed — a half-written or
    conflicted file raised a bare JSONDecodeError (defect log, 2026-10-09)."""
    try:
        return json.loads(_DUR.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ `.test_durations` n'est pas du JSON lisible ({exc}) — écriture "
              "interrompue ou conflit de fusion. Remède : `git checkout -- .test_durations` "
              "si rien n'y est à garder, puis `make test-durations-missing`.")
        return None


def collection_errors(stdout: str) -> list[str]:
    """The test files pytest failed to import, from its `--collect-only -q` output."""
    return sorted({ligne.split()[1] for ligne in stdout.splitlines()
                   if ligne.startswith("ERROR tests/")})


def _git_files(*args: str) -> set[str]:
    r = subprocess.run(["git", "ls-files", *args],
                       capture_output=True, text=True, cwd=str(_ROOT))
    return {ligne.strip() for ligne in r.stdout.splitlines() if ligne.strip()}


def untracked_files() -> set[str]:
    """Every file git does not track, ignored ones aside — what a commit does not carry.

    R251 (2026-09-27). R250 scoped the hook to the STAGED files. Too narrow: a test's id
    can be built from ANOTHER file's content — `test_a_comment_names_a_test_that_exists`
    puts a line number of the file it reads into its id — so a comment added to one
    staged file renamed a test in an unstaged one, and main went red (0dee1d41). At commit
    time pre-commit has already stashed every unstaged change: the tree IS the commit,
    plus the untracked files. Those, and only those, are not this commit's.

    2026-10-04: no `tests/` pathspec any more. About ten TRACKED tests parametrize over
    `src/`, `src/dashboard/views/` and `tools/` by walking the disk, so an untracked
    `src/dashboard/views/wip.py` adds ids to tracked files exactly as a test file does."""
    return _git_files("--others", "--exclude-standard")


def tracked_names() -> set[str]:
    """Every name a TRACKED path answers to: its components, basenames and stems."""
    noms: set[str] = set()
    for chemin in _git_files():
        for part in Path(chemin).parts:
            noms.update((part, Path(part).stem))
    return noms


def _names(path: str, tracked: set[str]) -> set[str]:
    """What an id param may call an untracked file: its path always; its basename and
    stem only when no tracked path answers to them (`[__init__.py]` names nobody). A
    stem shorter than 3 characters is never a name: a scratch `x.py` would otherwise
    claim the `x` of R251's own id `[tests/…-310-x]`."""
    p = Path(path)
    souche = {p.stem} if len(p.stem) >= 3 else set()
    return {path} | (({p.name} | souche) - tracked)


def _tokens(param: str) -> set[str]:
    """Every run of `-`-joined pieces of a pytest param, each also without the integer
    suffix pytest adds to duplicate ids (`wip.py0`). Exact pieces — `310` and `x` in
    `[tests/f.py-310-x]` are tokens, never substrings of a path."""
    morceaux = param.split("-")
    runs = {"-".join(morceaux[i:j]) for i in range(len(morceaux))
            for j in range(i + 1, len(morceaux) + 1)}
    return (runs | {t.rstrip("0123456789") for t in runs if t[-1:].isdigit()}) - {""}


def outside(node_ids, excluded: set[str], tracked: set[str] = frozenset()) -> list[str]:
    """The node-ids that name no excluded file — neither as their FILE nor in their
    `[param]` (path, or basename/stem no tracked path shares). Pure.

    2026-10-04: three tracked tests (`test_no_test_deletes_a_module`, `test_no_test_
    stubs_an_installed_package`, `test_the_http_escape_hatch_stays_narrow`) put every
    test file they find on disk in their ids; the file-only predicate let another
    session's untracked test refuse commits that did not touch it."""
    noms: set[str] = set()
    for f in excluded:
        noms |= _names(f, tracked)

    def nomme(k: str) -> bool:
        if k.split("::")[0] in excluded:
            return True
        if "[" not in k or not k.endswith("]"):
            return False
        return bool(_tokens(k[k.index("[") + 1:-1]) & noms)

    return [k for k in node_ids if not nomme(k)] if noms else list(node_ids)


def fix(fantomes: dict, sans: list[str]) -> int:
    """Repair `.test_durations` in place: drop the phantom entries, then run ONLY the
    uncollected-without-duration node-ids, in series, with `--store-durations` —
    pytest-split merges, so every other entry stays. Seconds, where `make
    test-durations` re-runs the whole suite in series (297 s).

    Added 2026-09-26: main's CI was red all night on this check and on its file-level
    twin, and the only remedy named was the full serial run.
    """
    durees = load_durations()
    if durees is None:
        return 1
    for k in fantomes:
        durees.pop(k, None)
    _DUR.write_text(json.dumps(durees, sort_keys=True, indent=4) + "\n", encoding="utf-8")
    print(f"   {len(fantomes)} entrée(s) fantôme(s) retirée(s)")
    if not sans:
        return 0
    print(f"   {len(sans)} test(s) à mesurer, en série…")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", *sans, "-q", "-p", "no:randomly",
         "--store-durations"], cwd=str(_ROOT), timeout=1200)
    return 0 if r.returncode in (0, 1) else r.returncode


def _collect() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:randomly",
         "--collect-only"],
        capture_output=True, text=True, cwd=str(_ROOT), timeout=600)


def _named(ids, hors: set[str], noms: set[str]) -> list[str]:
    """The ids that DO name an untracked file — the complement of `outside`."""
    gardes = set(outside(ids, hors, noms))
    return sorted(k for k in ids if k not in gardes)


def _list(titre: str, ids: list[str]) -> None:
    print(titre)
    for k in ids[:10]:
        print(f"   {k}")
    if len(ids) > 10:
        print(f"   … et {len(ids) - 10} autre(s)")


def _refuse_staged_entries_for_untracked(durees: dict, hors, noms) -> int:
    """Second line: a STAGED `.test_durations` must not carry durations for files the
    commit does not carry — CI would read them as phantoms (ci.yml runs this script with
    no argument, so with no exclusion). `make test-durations-missing` still writes them
    on purpose, for the author who measures before `git add`; this is where they stop."""
    souillees = _named(durees, hors, noms)
    if not souillees:
        return 0
    _list(f"❌ `.test_durations` est indexé avec {len(souillees)} durée(s) de fichiers NON "
          "suivis — la CI les lirait comme des fantômes :", souillees)
    print("\n   Remède : `git add` ces fichiers dans ce commit, ou désindexer ces lignes "
          "(`git add -p .test_durations`).")
    return 1


def _report(fantomes: dict, sans: list[str]) -> None:
    if fantomes:
        masse = sum(fantomes.values())
        print(f"❌ {len(fantomes)} entrée(s) non collectable(s), {masse:.1f} s de temps "
              "attribué à des tests qui n'existent plus :")
        for k, v in sorted(fantomes.items(), key=lambda x: -x[1])[:10]:
            print(f"   {v:6.2f} s  {k}")
        if len(fantomes) > 10:
            print(f"   … et {len(fantomes) - 10} autre(s)")
    if sans:
        _list(f"❌ {len(sans)} test(s) collecté(s) sans durée connue — `pytest-split` "
              "leur donne une durée MOYENNE :", sans)


def _scope(argv: list[str]) -> tuple[list[str], bool, set[str], set[str]]:
    """R251 — in the commit hook (staged files passed), what is UNTRACKED is not this
    commit's: neither a test in progress beside it, nor the ids a tracked test builds
    from it. `--fix` computes the same set, to WARN, never to filter."""
    fichiers = [a for a in argv[1:] if not a.startswith("-")]
    hook = bool(fichiers)
    hors = untracked_files() if hook or "--fix" in argv else set()
    return fichiers, hook, hors, (tracked_names() if hors else set())


def main() -> int:
    if not _DUR.is_file():
        print("❌ `.test_durations` absent — `pytest-split` répartirait sur le NOMBRE "
              "de tests. Remède : `make test-durations`.")
        return 1

    r = _collect()
    collectes = {ligne.strip() for ligne in r.stdout.splitlines()
                 if "::" in ligne and ligne.strip().startswith("tests/")}

    if len(collectes) < 1000:
        print(f"❌ la collecte n'a rendu que {len(collectes)} test(s) — elle a échoué, "
              "et ce contrôle serait vert sur n'importe quel fichier de durées.\n"
              f"   code de sortie pytest : {r.returncode}\n"
              f"   {r.stdout[-400:]}")
        return 1

    fichiers, hook, hors, noms = _scope(sys.argv)
    # A file that fails to IMPORT is absent from the collection, so every duration it
    # owns reads as a phantom. On 2026-09-25 that is how a missing FERNET_KEY in this
    # job was reported: 37 "tests that no longer exist" in two files that exist.
    erreurs = outside(collection_errors(r.stdout), hors if hook else set(), noms)
    if erreurs:
        print(f"❌ la collecte a échoué sur {len(erreurs)} fichier(s) — leurs durées "
              "passeraient pour des fantômes. Ce n'est pas `.test_durations` qui est "
              "faux, c'est l'environnement de ce job :")
        for f in erreurs:
            print(f"   {f}")
        print(f"\n{r.stdout[-1500:]}")
        return 1

    durees = load_durations()
    if durees is None:
        return 1
    if hook and ".test_durations" in fichiers and \
            _refuse_staged_entries_for_untracked(durees, hors, noms):
        return 1
    fantomes = {k: v for k, v in durees.items() if k not in collectes}
    sans = sorted(collectes - set(durees))
    tous_fantomes = fantomes
    sans, fantomes = inherited(sans, fantomes, durees, collectes)
    laisses = _named([*fantomes, *sans], hors, noms)
    if hook:
        # Neither judged NOR measured by `--fix-once`: the hook never writes a duration
        # for a file the commit does not carry.
        fantomes = {k: fantomes[k] for k in outside(fantomes, hors, noms)}
        sans = outside(sans, hors, noms)
        if laisses:
            _list(f"▶ {len(laisses)} id(s) laissé(s) hors — ils nomment un fichier non "
                  "suivi :", laisses)

    if not fantomes and not sans:
        print(f"▶ durations: {len(durees)} entrée(s), {len(collectes)} test(s) collecté(s)")
        print("✅ chaque durée désigne un test collecté, et chaque test a une durée")
        return 0

    _report(fantomes, sans)
    if "--fix" in sys.argv:
        if laisses:
            _list(f"⚠️ {len(laisses)} de ces durées appartiennent à des fichiers HORS de "
                  "l'index — ne commitez `.test_durations` qu'avec eux (le hook refuse "
                  "sinon) :", laisses)
        print("\n→ --fix")
        return fix(tous_fantomes, sans) or main_check_again()
    if "--fix-once" in sys.argv:
        return fix_once(fantomes, sans)
    print("\n   Remède : `make test-durations-missing` — retire les fantômes et mesure "
          "les SEULS tests sans durée, en série (pytest-split FUSIONNE) ; ou "
          "`make test-durations` pour tout régénérer.")
    return 1


def fix_once(fantomes: dict, sans: list[str], fixer=None, recheck=None) -> int:
    """The commit hook's remedy: measure, then REFUSE once. Always 1.

    R319 (2026-09-29): the hook refused 13 commits in 3 days for a new test run by plain
    pytest, each time naming a remedy to type by hand. It now measures them itself and
    fails ONCE, like `ruff --fix`: the file changed, the human re-stages it knowingly
    (code-critic R319 — never a silent `git add`, never a 0 after a rewrite).
    """
    print("\n→ mesure des tests sans durée (hook, --fix-once)")
    if (fixer or fix)(fantomes, sans) or (recheck or main_check_again)():
        return 1
    print("\n✅ `.test_durations` complété — `git add .test_durations` puis recommite "
          "(durées mesurées en série sur cette machine).")
    return 1


def main_check_again() -> int:
    """After a fix, the verdict comes from a fresh collection, not from the fix."""
    sys.argv = [a for a in sys.argv if a not in ("--fix", "--fix-once")]
    return main()


if __name__ == "__main__":
    raise SystemExit(main())
