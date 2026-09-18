"""Non-regression floor for the two-file roadmap.

Installed 2026-08-03, when the single 891-line `checklist.md` was split into an
active file (19 open items) and an archive (214 delivered ones). Every number
below was TRUE at the split.

The failure this guards against is specific and was named before it happened: a
rotation that **shrinks the denominator** improves the completion percentage
without delivering anything. Moving an item from active to archive must leave the
total untouched; deleting one must not be silently indistinguishable from
finishing one.

Raise a floor when the real number rises. Never lower one to make a test pass —
lowering it is the regression this file exists to catch.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.code_text import code_of

import pytest


def _repo_root() -> Path:
    """Walk up to the directory that owns .claude/ — never a fixed parents[N]."""
    for d in [Path(__file__).resolve()] + list(Path(__file__).resolve().parents):
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ found above this test — is it installed in the right repo?")


REPO = _repo_root()
ROADMAP = REPO / ".claude" / "dev-docs" / "roadmap"
ACTIVE = ROADMAP / "checklist.md"
ARCHIVE = ROADMAP / "archive.md"

_OPEN = re.compile(r"^\s*- \[ \]", re.M)
_DONE = re.compile(r"^\s*- \[[xX]\]", re.M)

# Measured at the 2026-08-03 split: 19 open + 221 done = 240 items total,
# of which 214 delivered ones landed in the archive.
_TOTAL_ITEMS_FLOOR = 240
_ARCHIVE_DONE_FLOOR = 214


def _counts(p: Path) -> tuple[int, int]:
    t = p.read_text(encoding="utf-8")
    return len(_OPEN.findall(t)), len(_DONE.findall(t))


def test_both_roadmap_files_exist():
    """Rule 17 names two files. A rotation into a file that is not there is a no-op."""
    assert ACTIVE.exists(), f"active roadmap missing: {ACTIVE}"
    assert ARCHIVE.exists(), f"roadmap archive missing: {ARCHIVE}"


def test_the_rotation_does_not_shrink_the_denominator():
    """Active + archive must conserve every item. Moving is not deleting.

    This is the whole point of the two-file split: a percentage computed over a
    set that quietly loses members reports progress that never happened.
    """
    a_open, a_done = _counts(ACTIVE)
    r_open, r_done = _counts(ARCHIVE)
    total = a_open + a_done + r_open + r_done
    assert total >= _TOTAL_ITEMS_FLOOR, (
        f"the two roadmap files now hold {total} items, below the {_TOTAL_ITEMS_FLOOR} "
        f"measured at the split (actif {a_open + a_done}, archive {r_open + r_done}). "
        "An item was deleted rather than rotated — or a floor was lowered to hide it."
    )


def test_the_archive_holds_nothing_actionable():
    """An open item in the archive is work nobody will look at again.

    `/resume` and `/sprint` read the active file only. An unchecked box that
    rotates out stops being scheduled without ever being decided.
    """
    r_open, _ = _counts(ARCHIVE)
    assert r_open == 0, (
        f"{r_open} unchecked item(s) in {ARCHIVE.name} — the archive is passive by "
        "contract. Move them back to checklist.md, or close them explicitly."
    )


def test_the_archive_keeps_what_was_delivered():
    """The archive is append-mostly. Losing history is how a class gets rediscovered."""
    _, r_done = _counts(ARCHIVE)
    assert r_done >= _ARCHIVE_DONE_FLOOR, (
        f"archive holds {r_done} delivered items, below the {_ARCHIVE_DONE_FLOOR} "
        "measured at the split — delivered work was erased, not archived."
    )


def test_the_active_file_stays_the_one_that_is_read():
    """Both files must name each other, or a reader lands on half the truth."""
    active_txt = code_of(ACTIVE)
    archive_txt = code_of(ARCHIVE)
    assert "archive.md" in active_txt, (
        "checklist.md never names archive.md — a reader cannot know the other half exists"
    )
    assert "checklist.md" in archive_txt, (
        "archive.md never names checklist.md — a reader landing here has no way back "
        "to what is actually open"
    )


def test_no_brick_id_vanishes_from_both_files() -> None:
    """Une brique retirée de l'actif doit se retrouver dans l'archive. Jamais nulle part.

    C'est la règle « déplacement, pas suppression » de CLAUDE.md, et elle n'était
    tenue par rien. Mesuré le 2026-09-12 : une rotation a retiré R92, R93 et R95 de
    `checklist.md` sans les écrire dans `archive.md` — les trois blocs ont disparu du
    dépôt, et les cinq tests de ce fichier sont restés verts. Le plancher de
    conservation ne compte que des ITEMS ; il ne remarque pas qu'un identifiant
    précis s'est évaporé, parce que d'autres lignes avaient été ajoutées ailleurs.

    Le garde compare donc les identifiants présents dans le dépôt à ceux du commit
    précédent : aucun ne doit sortir des deux fichiers à la fois.
    """
    import re
    import subprocess

    def _ids(text: str) -> set[str]:
        """Les identifiants PORTÉS, pas ceux mentionnés.

        La première version prenait tout identifiant `R` suivi de chiffres, donc la phrase « R92 à R95 »
        du récit suffisait à la satisfaire : la mutation qui supprimait vraiment le
        bloc R92 restait verte. On ne compte donc qu'un bloc (`- [ ] **R92 —`,
        coché ou non) ou une ligne d'index (`| R92 |`).
        """
        return (set(re.findall(r"^- \[[ x]\] \*\*(R\d{1,3}) ", text, re.M))
                | set(re.findall(r"^\|\s*(R\d{1,3})\s*\|", text, re.M)))

    here = _ids(code_of(ACTIVE)) | _ids(code_of(ARCHIVE))

    before_txt = ""
    for path in (ACTIVE, ARCHIVE):
        rel = path.relative_to(REPO).as_posix()
        res = subprocess.run(["git", "show", f"HEAD:{rel}"],
                             cwd=REPO, capture_output=True, text=True)
        if res.returncode != 0:
            pytest.skip(f"{rel} n'est pas encore suivi par git")
        before_txt += res.stdout
    before = _ids(before_txt)

    vanished = sorted(before - here, key=lambda r: int(r[1:]))
    assert not vanished, (
        f"identifiant(s) présents au commit précédent et désormais dans AUCUN des "
        f"deux fichiers : {vanished}. Une brique se DÉPLACE de l'actif vers "
        "l'archive ; la retirer des deux efface le travail et l'explication avec.")


def test_the_active_file_does_not_carry_a_section_twice() -> None:
    """La rotation ne peut que RÉTRÉCIR le fichier — la duplication, elle, le grossit.

    Ajouté le 2026-09-16, après un défaut vrai : une réécriture des blocs R115/R116 a
    recopié **toute la fin du fichier** (664 → 1104 lignes, R117 et le bloc de reprise en
    double). Les six gardes de ce fichier sont passés VERTS, parce qu'ils regardent tous
    dans l'autre sens : `test_the_rotation_does_not_shrink_the_denominator` échoue si la
    somme diminue, et une duplication l'augmente.

    C'est la forme « un garde qui ne regarde que la direction dans laquelle on s'est
    déjà trompé ». Le contrôle qui manquait est trivial : un identifiant de brique, un
    marqueur de reprise et un titre de section n'apparaissent qu'une fois.
    """
    import collections
    import re

    text = code_of(ACTIVE)

    marks = re.findall(r"<!--\s*reprise:\s*open=", text)
    assert len(marks) <= 1, (
        f"{len(marks)} blocs de reprise dans {ACTIVE.name} — le fichier a été recopié "
        "sur lui-même. `/resume` lirait le premier et ignorerait tout ce qui suit.")

    headings = [h.strip() for h in re.findall(r"^#{2,3} (.+)$", text, re.M)]
    dup_h = [h for h, n in collections.Counter(headings).items() if n > 1]
    assert not dup_h, f"titre(s) de section en double dans {ACTIVE.name} : {dup_h}"

    tasks = re.findall(r"^- \[[ x]\] \*\*(R\d+)\b", text, re.M)
    dup_t = [t for t, n in collections.Counter(tasks).items() if n > 1]
    assert not dup_t, (
        f"brique(s) déclarée(s) deux fois dans {ACTIVE.name} : {dup_t}. Deux blocs pour "
        "une même brique divergent, et on corrige celui que la recherche trouve en "
        "premier.")


def test_the_duplication_detector_is_not_vacuous() -> None:
    """Non-vacuité : sur un fichier VOLONTAIREMENT doublé, le détecteur doit mordre.

    Sans elle, une expression régulière qui ne matche plus rien rendrait le garde
    ci-dessus vert à vide — c'est exactement ainsi qu'il a manqué le défaut du
    2026-09-16.
    """
    import collections
    import re

    text = code_of(ACTIVE)
    assert re.search(r"^- \[[ x]\] \*\*R\d+\b", text, re.M), (
        "l'expression des briques ne matche RIEN dans le fichier actif — le détecteur "
        "de duplication ne peut plus rien voir")

    doubled = text + text
    assert len(re.findall(r"<!--\s*reprise:\s*open=", doubled)) > 1
    tasks = re.findall(r"^- \[[ x]\] \*\*(R\d+)\b", doubled, re.M)
    assert [t for t, n in collections.Counter(tasks).items() if n > 1], (
        "un fichier concaténé avec lui-même ne produit aucun doublon détecté")
