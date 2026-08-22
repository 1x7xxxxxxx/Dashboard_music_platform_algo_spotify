"""Guard: multi-tenant DAGs must isolate per-artist failures (no fleet poisoning).

Type: Utility
Error class `multitenant-dag-fleet-poisoning` (.claude/dev-docs/error-classes.md).
Benken incident 2026-06-19: a per-tenant loop `for artist_id, ... in get_active_artists()`
that raises on one bad tenant failed the whole DAG for ALL tenants. The fix wraps each
iteration body in try/except-continue. This test fails CI if a NEW artist-loop ships
without that isolation, so the class can't silently return.
"""
import ast
from pathlib import Path

import pytest

_DAGS_DIR = Path(__file__).resolve().parent.parent / "airflow" / "dags"


# What makes a loop a FLEET loop. Widened 2026-08-22 — the original test was
# "does the target bind a variable literally called `artist_id`", which is a
# hand-written scope with two measured evasions in `alert_monitor.py` alone:
#
#   check_onboarding_readiness:  `for aid, name in get_active_artists(...)`
#                                — the name is `aid`, so the guard never looked at it
#   check_data_freshness:        `[(aid, name, check_freshness(db, aid))
#                                   for aid, name in get_active_artists()]`
#                                — a list COMPREHENSION, not an ast.For at all
#
# The second was genuinely unisolated: one `CredentialLoadError` fails the task, and
# `send_consolidated_alert` has `trigger_rule='all_done'`, so the mail still goes out
# with the whole per-tenant section silently missing. Matching on the ITERATOR — a
# call to `get_active_artists` — cannot be evaded by renaming the loop variable.
_FLEET_SOURCES = {"get_active_artists"}


def _iterates_the_fleet(iter_node: ast.AST) -> bool:
    for n in ast.walk(iter_node):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name in _FLEET_SOURCES:
                return True
    return False


def _artist_loops(tree: ast.AST):
    """Yield every loop over the tenant fleet — `for` statements AND comprehensions.

    A loop qualifies if its target binds `artist_id` (the original rule, kept) or if
    it iterates a call to `get_active_artists` whatever it names the variable.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            names = {n.id for n in ast.walk(node.target) if isinstance(n, ast.Name)}
            if "artist_id" in names or _iterates_the_fleet(node.iter):
                yield node
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                               ast.GeneratorExp)):
            if any(_iterates_the_fleet(g.iter) for g in node.generators):
                yield node


def _body_nodes(loop):
    """Every node in the loop's body — statements for a `for`, the element+conditions
    for a comprehension (which has no body, and that is exactly the point: a
    comprehension CANNOT contain a try, so one that touches `db` is unisolated by
    construction)."""
    if isinstance(loop, ast.For):
        return list(ast.walk(ast.Module(body=loop.body, type_ignores=[])))
    parts = [loop.elt] if hasattr(loop, "elt") else []
    if isinstance(loop, ast.DictComp):
        parts = [loop.key, loop.value]
    for gen in loop.generators:
        parts.extend(gen.ifs)
    return [n for part in parts for n in ast.walk(part)]


def _has_try(loop) -> bool:
    """True if the loop body contains a Try (per-iteration isolation).

    Always False for a comprehension: Python has no syntax for a try inside one, so
    a comprehension over the fleet that touches `db` can only be made safe by being
    rewritten as a statement loop.
    """
    return any(isinstance(n, ast.Try) for n in _body_nodes(loop))


def _touches_db(loop) -> bool:
    """True if the loop body references `db` (a per-tenant DB/collector call that can raise).

    Pure aggregation loops (logger.warning / list.append over already-fetched rows) never
    reference `db`, so they can't fail per-tenant and need no isolation. A loop that calls
    db.fetch_query / db.upsert_many or passes `db` into a work function (score_all_songs,
    label_predictions, detect_saves_resurrection, …) DOES per-tenant work → must isolate.
    """
    return any(isinstance(n, ast.Name) and n.id == "db" for n in _body_nodes(loop))


_DAG_FILES = sorted(_DAGS_DIR.glob("*.py"))


@pytest.mark.parametrize("dag_file", _DAG_FILES, ids=lambda p: p.name)
def test_artist_loops_are_isolated(dag_file):
    tree = ast.parse(dag_file.read_text(encoding="utf-8-sig"))
    violations = [
        f"{dag_file.name}:{loop.lineno} — per-tenant `db` work in an artist loop with no try/except"
        for loop in _artist_loops(tree)
        if _touches_db(loop) and not _has_try(loop)
    ]
    assert not violations, (
        "Fleet-poisoning risk — wrap each per-tenant iteration in try/except-continue so one "
        "bad tenant can't fail the DAG for all (see youtube_daily.py / soundcloud_daily.py):\n  "
        + "\n  ".join(violations)
    )
