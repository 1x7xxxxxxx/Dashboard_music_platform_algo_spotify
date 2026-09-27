"""R269 — a function body is written once; the copies only become fewer.

Type: Test
Uses: tools/dev/duplicate_functions.py (groups, repo_files)

Measured 2026-09-27 (owner notes L166) : 5 groups / 11 sites of the same body across
src/, airflow/dags/ and tools/ — four tenant totals in kpi_helpers with the same `except`,
two snapshot readers, the Apple plays/Shazams pair (the Shazam copy was once left behind
by a fix), two reopen probes. Four groups factored the same day ; what remains is the DAG
failure-callback pair, which R265 factors with the other ten callbacks.

Mutation record (2026-09-27) : one copy of a kpi reader pasted back → the ratchet went red ;
the literal blanking removed → the synthetic pair differing by a table name is missed → red ;
the statement floor removed → two different one-line queries counted as copies → red.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("duplicate_functions", ROOT / "tools/dev/duplicate_functions.py")
dup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dup)

CEILING_SITES = 2

_COPY = '''
def {name}(db, artist_id):
    """doc {name}"""
    try:
        row = db.fetch_query("SELECT SUM(x) FROM {table} WHERE a = %s", (artist_id,))
        # a comment that differs
        return int(row[0][0] or 0)
    except Exception as exc:
        log("{table} unreadable", exc)
        return None
'''


def test_the_copies_only_become_fewer():
    sites = sum(len(g) for g in dup.groups(dup.repo_files()))
    assert sites <= CEILING_SITES, (
        f"{sites} sites de fonctions dupliquées (plafond {CEILING_SITES}) — "
        "`python3 tools/dev/duplicate_functions.py` les liste ; factoriser")


def test_the_detector_sees_a_copy_that_changed_only_its_strings():
    files = [("a.py", _COPY.format(name="f", table="t1")),
             ("b.py", _COPY.format(name="g", table="t2"))]
    assert dup.groups(files) == [["a.py:2 f", "b.py:2 g"]]


def test_two_different_one_line_queries_are_not_a_copy():
    one = 'def {n}(db, a):\n    return db.fetch_df(\n        """\n        SELECT {c}\n        FROM t\n        WHERE a = %s\n        """,\n        (a,),\n    )\n'
    files = [("a.py", one.format(n="f", c="x")), ("b.py", one.format(n="g", c="y"))]
    assert dup.groups(files) == []
