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


def _artist_loops(tree: ast.AST):
    """Yield every `for` loop whose target binds an `artist_id` variable."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        names = {n.id for n in ast.walk(node.target) if isinstance(n, ast.Name)}
        if "artist_id" in names:
            yield node


def _body_nodes(loop: ast.For):
    return list(ast.walk(ast.Module(body=loop.body, type_ignores=[])))


def _has_try(loop: ast.For) -> bool:
    """True if the loop body contains a Try (per-iteration isolation)."""
    return any(isinstance(n, ast.Try) for n in _body_nodes(loop))


def _touches_db(loop: ast.For) -> bool:
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
