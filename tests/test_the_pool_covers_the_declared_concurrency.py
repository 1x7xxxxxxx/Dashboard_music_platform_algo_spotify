"""REQ-RUN-06 — the connection pool covers the declared concurrency and stays bounded (R367).

ADR-030 sizes the pool at 8 per process (dashboard, API) and reopens a larger one when
Postgres connections in use pass 50 % of `max_connections` (100). A render opens exactly
one connection (`view_session()`, rule 9), so a pool of N serves N concurrent renders
before the monitored direct fallback (`ConnectionPoolExhausted`) takes over.

Two-sided, read in the AST of every `enable_pool(...)` call under `src/`:
  * each `maxconn` ≥ the declared concurrency — the pool does not silently shrink;
  * the sum over processes ≤ half of `max_connections` — the ADR-030 trigger is not
    crossed by a config edit that nobody measured;
and the overflow is watched: the alert exists. No call site seen ⇒ red, never vacuous.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DECLARED_CONCURRENT_RENDERS = 8   # per process — ADR-030, « 8 per dashboard instance »
PG_MAX_CONNECTIONS = 100          # prod pg_stat_activity, ADR-030 measure table
CONNECTIONS_PER_RENDER = 1        # view_session(), CLAUDE.md rule 9


def pool_sizes(source: str) -> list[int]:
    """`maxconn` of every enable_pool(...) call (keyword or 2nd positional). Pure."""
    sizes = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id",
                getattr(node.func, "attr", None)) == "enable_pool"):
            continue
        kw = {k.arg: k.value for k in node.keywords}
        value = kw.get("maxconn") or (node.args[1] if len(node.args) > 1 else None)
        assert isinstance(value, ast.Constant), (
            f"enable_pool at line {node.lineno}: maxconn must be a literal to be measured")
        sizes.append(value.value)
    return sizes


def measured() -> dict[str, list[int]]:
    out = {}
    for f in sorted((REPO / "src").rglob("*.py")):
        sizes = pool_sizes(f.read_text(encoding="utf-8"))
        if sizes:
            out[str(f.relative_to(REPO))] = sizes
    return out


def test_every_pool_covers_the_declared_concurrency_and_stays_bounded() -> None:
    sites = measured()
    assert sites, "no enable_pool(...) call seen — the reader is blind, or the pool is gone"
    need = CONNECTIONS_PER_RENDER * DECLARED_CONCURRENT_RENDERS
    small = {f: s for f, s in sites.items() if min(s) < need}
    assert not small, f"pool below the declared concurrency ({need}): {small}"
    total = sum(max(s) for s in sites.values())
    assert total <= PG_MAX_CONNECTIONS // 2, (
        f"pools sum to {total} > {PG_MAX_CONNECTIONS // 2} (50 % of max_connections): the "
        "ADR-030 trigger is crossed — measure pg_stat_activity before growing a pool")


def test_the_pool_overflow_is_watched() -> None:
    rules = (REPO / "deploy" / "prometheus" / "rules" / "streamlytics.yml").read_text(encoding="utf-8")
    assert "alert: ConnectionPoolExhausted" in rules


def test_the_detector_sees_a_pool_size_in_both_forms() -> None:
    assert pool_sizes("enable_pool(minconn=1, maxconn=8)\n") == [8]
    assert pool_sizes("from x import enable_pool\nenable_pool(1, 3)\n") == [3]
    assert pool_sizes("h.enable_pool(maxconn=2)\n") == [2]
    assert pool_sizes("# enable_pool(maxconn=99)\nX = 1\n") == []
