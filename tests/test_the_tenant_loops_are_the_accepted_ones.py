"""REQ-ORCH-01 — every per-tenant loop inside a collection task is an ACCEPTED one (R367).

The fan-out (one task per tenant) is deferred by ADR-030 behind a trigger watched every
night (`reopen_check.py` « fan-out par locataire »). The debt is accepted, so this probe
does not fail on it: it MEASURES it. It fails on two things only —
  * a NEW tenant loop in a `*_daily.py` DAG (the debt grew without being declared);
  * a site of the accepted set that no longer exists (the debt shrank: shrink the set);
and it fails if its predicate sees no site at all, so a blind reader cannot pass.

A tenant loop is a `for` whose target names a tenant id, read in the AST — never a text
search, which would match this docstring.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TENANT_NAMES = frozenset({"artist_id", "aid", "saas_artist_id", "tid"})

# (file, function) — measured 2026-10-05. Leaving this set is the fan-out of R284.
ACCEPTED = frozenset({
    ("instagram_daily.py", "precheck_instagram_credentials"),
    ("instagram_daily.py", "run_insta_collector"),
    ("meta_ads_api_daily.py", "run_meta_api_collector"),
    ("ml_scoring_daily.py", "run_ml_scoring"),
    ("soundcloud_daily.py", "precheck_soundcloud_credentials"),
    ("soundcloud_daily.py", "run_soundcloud_collector"),
    ("spotify_api_daily.py", "collect_spotify_artists"),
    ("spotify_api_daily.py", "collect_spotify_top_tracks"),
    ("youtube_daily.py", "collect_youtube_data"),
})


def tenant_loops(source: str) -> set[str]:
    """Names of the functions that loop over tenants. Pure."""
    found = set()
    for fn in ast.walk(ast.parse(source)):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.For) and any(
                    isinstance(n, ast.Name) and n.id in TENANT_NAMES
                    for n in ast.walk(node.target)):
                found.add(fn.name)
    return found


def measured() -> set[tuple[str, str]]:
    return {(f.name, name) for f in sorted((REPO / "airflow" / "dags").glob("*_daily.py"))
            for name in tenant_loops(f.read_text(encoding="utf-8"))}


def test_every_tenant_loop_is_an_accepted_one() -> None:
    sites = measured()
    assert sites, "the predicate sees no tenant loop at all — the reader is blind, not the DAGs clean"
    new, gone = sites - ACCEPTED, ACCEPTED - sites
    assert not new, (f"new per-tenant loop(s) inside one task: {sorted(new)}. A slow tenant "
                     "delays every other one (REQ-ORCH-01). Fan out (.expand / one task per "
                     "tenant), or declare it in ACCEPTED with the reason.")
    assert not gone, f"accepted loop(s) no longer exist — shrink ACCEPTED: {sorted(gone)}"


def test_the_detector_sees_a_tenant_loop_and_ignores_others() -> None:
    assert tenant_loops("def f(artists):\n    for artist_id, n in artists:\n        pass\n") == {"f"}
    assert tenant_loops("def g(rows):\n    for (aid,) in rows:\n        pass\n") == {"g"}
    assert tenant_loops("def h(xs):\n    for x in xs:\n        pass\n") == set()
    assert tenant_loops("# for artist_id in artists:\nX = 1\n") == set()
