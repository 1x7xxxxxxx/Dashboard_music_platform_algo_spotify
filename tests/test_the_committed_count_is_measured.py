"""Guard: le compte affiché après un import est MESURÉ, pas déclaré.

Type: Utility
Uses: ast, src.dashboard.views.upload_csv
Triggers: pytest
Persists in: nothing

Error class `a-count-that-is-claimed-not-measured`.

« It's always good practice to run validation on the data models that are built at
  the end of a pipeline. There are three things you can check on: […] **checking row
  count growth (or reduction) in the data model**. »
        — Densmore, *Data Pipelines Pocket Reference*, p. 218

Petrella (*Fundamentals of Data Observability*, p. 180) nomme les deux chiffres à
confronter : « get the overall **emitted** record count » et « get the overall
**committed** record count ».

Nous n'avions que le premier. `upsert_many` renvoie `len(data)` — le nombre de
lignes ENVOYÉES, après déduplication — et son propre commentaire le dit : le
`rowcount` de `execute_batch` ne reflète que le dernier lot. Ce chiffre remonte
jusqu'au « ✅ N ligne(s) importée(s) » de l'écran et jusqu'à `csv_upload_log`. Il
n'a jamais rien mesuré : si la base en accepte moins, il ne bouge pas.

La mesure se fait à la DESTINATION, autour de l'écriture, sans toucher au chemin
d'écriture qu'empruntent les seize DAGs — un `COUNT(*)` avant et après.

Une différence n'est pas une anomalie : un ré-import met à jour sans ajouter, et
« 0 nouvelle » sur 400 lignes traitées est alors la bonne réponse. Ce qui manquait
n'était pas une alerte, c'était le chiffre.
"""
from __future__ import annotations

import ast
import functools
import pathlib

import pytest

_VIEW = pathlib.Path("src/dashboard/views/upload_csv.py")


@functools.lru_cache(maxsize=1)
def _tree() -> ast.Module:
    """L'AST de la vue, lu À L'APPEL et non à l'import.

    Une lecture au niveau module lève `FileNotFoundError` à la collecte le jour où
    le fichier surveillé disparaît : pytest rapporte alors « errors » sans nommer
    une seule des propriétés perdues. Cliquet du dépôt —
    `tests/test_a_test_file_is_collectable_without_what_it_watches.py`.
    """
    return ast.parse(_VIEW.read_text(encoding="utf-8"))


def _import_loop(tree: ast.Module | None = None) -> ast.For:
    """La boucle qui écrit les fichiers en base, trouvée par son appel à upsert_many."""
    for loop in [n for n in ast.walk(_tree() if tree is None else tree)
                 if isinstance(n, ast.For)]:
        for node in ast.walk(loop):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "upsert_many"):
                return loop
    pytest.fail("aucune boucle n'appelle upsert_many dans la vue — garde à repointer")


def test_the_destination_is_counted_on_both_sides_of_the_write():
    loop = _import_loop()
    calls = [n for n in ast.walk(loop)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_rows_in_table"]
    assert len(calls) >= 2, (
        "le compte de destination doit être pris AVANT et APRÈS l'écriture : un seul "
        f"appel ne mesure rien ({len(calls)} trouvé). Sans les deux, le chiffre "
        "affiché reste celui qu'on a envoyé, jamais celui que la base a reçu."
    )


def test_the_measured_delta_reaches_the_screen():
    """Mesurer sans afficher est le mode d'échec déjà payé cinq fois ici."""
    loop = _import_loop()
    assigned = {
        t.id for n in ast.walk(loop) if isinstance(n, ast.Assign)
        for t in n.targets if isinstance(t, ast.Name)
    }
    assert "added" in assigned, "le delta mesuré n'est pas nommé"

    used_in_dict = False
    for node in ast.walk(loop):
        if isinstance(node, ast.Dict):
            for value in node.values:
                for sub in ast.walk(value):
                    if isinstance(sub, ast.Name) and sub.id == "added":
                        used_in_dict = True
    assert used_in_dict, (
        "`added` est calculé et n'entre dans aucune ligne du tableau de résultat. "
        "Un constat qui n'atteint pas le lecteur ne vaut pas mieux que pas de constat "
        "— c'est la classe `finding-computed-but-never-sent`, appliquée à l'écran."
    )


def test_the_count_helper_validates_its_table():
    """`table` vient d'un registre en dur, mais l'allowlist reste obligatoire (règle #8)."""
    fn = next(n for n in ast.walk(_tree())
              if isinstance(n, ast.FunctionDef) and n.name == "_rows_in_table")
    names = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "validate_table" in names, (
        "un nom de table interpolé dans du SQL se valide contre l'allowlist avant "
        "exécution, même quand il vient d'une constante du module"
    )


def count_is_claimed(loop: ast.For) -> list[str]:
    """Why the number shown is the one SENT, not the one the base RECEIVED. Pure."""
    why = []
    counts = [n for n in ast.walk(loop) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Name) and n.func.id == "_rows_in_table"]
    if len(counts) < 2:
        why.append("destination not counted before AND after")
    shown = any(isinstance(sub, ast.Name) and sub.id == "added"
                for d in ast.walk(loop) if isinstance(d, ast.Dict)
                for v in d.values for sub in ast.walk(v))
    if not shown:
        why.append("measured delta never reaches the result row")
    return why


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity: the import loop before the fix — `len(rows)` shown as « importées »
    — is refused on both counts; the measured form is accepted."""
    claimed = ("for f in files:\n"
               "    rows = parse(f)\n"
               "    db.upsert_many(table, rows, keys)\n"
               "    results.append({'file': f.name, 'rows': len(rows)})\n")
    assert count_is_claimed(_import_loop(ast.parse(claimed))) == [
        "destination not counted before AND after",
        "measured delta never reaches the result row"]
    measured = ("for f in files:\n"
                "    rows = parse(f)\n"
                "    before = _rows_in_table(db, table, aid)\n"
                "    db.upsert_many(table, rows, keys)\n"
                "    added = _rows_in_table(db, table, aid) - before\n"
                "    results.append({'file': f.name, 'rows': added})\n")
    assert count_is_claimed(_import_loop(ast.parse(measured))) == []
    once = measured.replace("    added = _rows_in_table(db, table, aid) - before\n",
                            "    added = len(rows)\n")
    assert count_is_claimed(_import_loop(ast.parse(once))) == [
        "destination not counted before AND after"]


def test_the_real_import_loop_measures_what_it_shows():
    assert count_is_claimed(_import_loop()) == []
