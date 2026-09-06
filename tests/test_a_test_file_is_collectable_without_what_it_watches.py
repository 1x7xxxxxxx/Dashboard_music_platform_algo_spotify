"""Guard: deleting a watched file must FAIL a test, never un-collect a module.

Type: Utility
Uses: ast
Triggers: pytest
Persists in: nothing

Error class `module-level-read-turns-a-deletion-into-a-collection-error`.

Measured 2026-09-06. `views/process_guide.py` was deleted; four tests then reported
as `ERROR`, not as failures — `test_the_guide_is_fetchable_not_only_mailed.py` read
that file at MODULE level (`SRC = GUIDE_PAGE.read_text()`), so pytest raised
`FileNotFoundError` while importing the module, before a single assertion ran.

The difference matters more than it looks:

* a FAILURE names the property that was lost — « the page that carries the guide PDF
  left the navigation » — and points at the surface to re-anchor;
* a COLLECTION ERROR names a path and a `FileNotFoundError`. The summary line reads
  « 4 errors » and the four properties those tests defended are simply gone from the
  run, silently, along with every other test in the same module.

A ratchet rather than a rewrite: the five existing sites are legitimate reads of
files that exist today, and rewriting them all would be a change nobody asked for.
What the ratchet buys is that the SIXTH cannot be added — which is how this repo
already handles string-versus-source assertions.
"""
from __future__ import annotations

import ast
from pathlib import Path

# Gelé à la mesure du 2026-09-06. Cette liste ne peut que RACCOURCIR : retirer un
# site le retire d'ici, en ajouter un fait échouer ce test. Les cinq lisent des
# fichiers qui existent, et c'est précisément ce qui les rend invisibles jusqu'au
# jour où l'un d'eux disparaît.
_ACCEPTED = {
    "test_alert_subject_names_the_tenant.py",
    "test_every_named_guard_exists.py",
    "test_every_nightly_check_is_scheduled_and_heard.py",
    "test_the_guide_is_fetchable_not_only_mailed.py",
    "test_two_checks_one_question.py",
}


def _module_level_reads(path: Path) -> list[int]:
    """Lignes des AFFECTATIONS de module qui lisent un fichier.

    Les `def` et `class` du niveau module ne comptent pas : leur corps ne s'exécute
    pas à l'import, donc un fichier manquant y produit un échec de test — ce qu'on
    veut — et non une erreur de collecte.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:                     # pragma: no cover
        return []
    out = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        for sub in ast.walk(node.value):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr in ("read_text", "read_bytes")):
                out.append(node.lineno)
                break
    return out


def _offenders() -> dict[str, list[int]]:
    here = Path(__file__).parent
    return {p.name: lines for p in sorted(here.glob("test_*.py"))
            if (lines := _module_level_reads(p))}


def test_no_new_module_level_read_of_a_watched_file():
    """Le cliquet : la liste ne peut que raccourcir."""
    added = sorted(set(_offenders()) - _ACCEPTED)
    assert not added, (
        f"{added} lisent un fichier au niveau MODULE. Le jour où ce fichier "
        "disparaît, pytest lève `FileNotFoundError` à l'import : le module entier "
        "cesse d'être collecté et le rapport dit « errors » sans nommer une seule "
        "des propriétés perdues. Déplace la lecture dans le test ou dans une "
        "fixture — un échec nomme ce qui a été perdu, une erreur de collecte non.")


def test_the_ratchet_does_not_name_files_that_are_already_clean():
    """Un cliquet qui garde des noms périmés se détend sans qu'on le voie."""
    stale = sorted(_ACCEPTED - set(_offenders()))
    assert not stale, (
        f"{stale} ne lisent plus rien au niveau module : retire-les de `_ACCEPTED`, "
        "sinon le cliquet autorise un site de plus qu'il n'en existe.")


def test_the_sweep_still_sees_something():
    """Sans site connu, les deux assertions ci-dessus sont vraies de rien."""
    assert _ACCEPTED, "le cliquet est vide — il ne garde plus rien"
    assert _offenders(), (
        "aucune lecture de module trouvée alors que le cliquet en déclare : le "
        "détecteur ne voit plus le motif qu'il surveille")
