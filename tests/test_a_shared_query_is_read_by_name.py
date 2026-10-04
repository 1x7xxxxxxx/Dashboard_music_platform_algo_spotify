"""A query shared across modules is read by NAME, never by position.

Type: Test
Uses: ast
Depends on: src/, airflow/
Persists in: nothing

Why this guard exists
---------------------
Measured 2026-10-04 (R369): R140 (5ddd7f6c, 2026-09-20) gave `mrr_by_plan_sql()` a fourth
column, `price_monthly`, at index 1. Its two callers had been switched to the helper by
their CALL and not by their SHAPE: `billing.py` and `admin.py` kept `sum(r[2])` for the
MRR (now the artist count), `sum(int(r[1]))` for the paying artists (now the price), and a
3-name `pd.DataFrame` that raised as soon as one paying human existed. 14 days, every
guard green, because CI's database is empty.

The property checked here is deliberately SMALL, so that it can be verified:

    in one function, the result of `<db>.fetch_query(X, ...)` — where X is a `*_sql()`
    call or a `*_SQL` name IMPORTED FROM ANOTHER MODULE — is subscripted by an integer,
    unpacked into a tuple, iterated into a tuple target, or handed to
    `pd.DataFrame(..., columns=...)`; directly, through the variable it is assigned to,
    or through a loop variable over that variable (`for r in rows: r[2]`).

A producer that lives in another module can change its SELECT list without the consumer's
file changing — that is the whole defect. A same-module SQL constant is edited next to
its reader; a `fetch_df` consumer reads names.

⚠️ This proves a positional read is DRAWN, not that it is WRONG (A24). The proof that the
MRR consumers BIND is `tests/test_the_mrr_has_one_definition.py::test_*_reads_the_mrr_by_
meaning`, which executes them on a row of the real shape. The sites below are aligned
TODAY; each is listed with its producer so that a reader sees what has to move together.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCOPES = ("src", "airflow")

#: Live positional readers of a cross-module query — aligned on 2026-10-04, read by hand.
#: Each one breaks silently if its producer gains or reorders a column. Not a fix: a list
#: the roadmap carries (R369 follow-up) until each consumer reads by name.
_KNOWN: dict[tuple[str, str], str] = {
    ("airflow/dags/weekly_digest.py", "SPOTIFY_WEEKLY_STREAMS_SQL"):
        "src/utils/digest_queries.py — 2 columns (last_7d, prev_7d), read [0][0]/[0][1]",
    ("airflow/dags/weekly_digest.py", "META_WEEKLY_SPEND_SQL"):
        "src/utils/digest_queries.py — 2 columns (spend, ctr), read [0][0]/[0][1]",
    ("airflow/dags/weekly_digest.py", "SOUNDCLOUD_WEEKLY_DELTA_SQL"):
        "src/utils/digest_queries.py — 2 columns (latest, week_ago), read [0][0]/[0][1]",
    ("src/dashboard/views/admin_activation.py", "activation_sql"):
        "src/utils/activation.py — 2 columns (actives, total), unpacked from rows[0]",
    ("src/dashboard/views/admin_activation.py", "dormant_tenants_sql"):
        "src/utils/activation.py — 6 columns, pd.DataFrame(columns=[6 names])",
}


def _imported_elsewhere(tree: ast.Module, module: str) -> set[str]:
    """Names brought in by `from X import n` with X another module (anywhere in the file)."""
    names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.module != module and n.level == 0:
            names.update(a.asname or a.name for a in n.names)
    return names


def _shared_query(call: ast.AST, shared: set[str]) -> str | None:
    """The shared SQL name if `call` is `<x>.fetch_query(<shared sql>, ...)`."""
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            and call.func.attr == "fetch_query" and call.args):
        return None
    a = call.args[0]
    if isinstance(a, ast.Call) and isinstance(a.func, ast.Name):
        a = a.func
        ok = a.id.endswith("_sql")
    else:
        ok = isinstance(a, ast.Name) and a.id.endswith("_SQL")
    return a.id if ok and a.id in shared else None


def _is_int_subscript(n: ast.AST) -> bool:
    return (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
            and isinstance(n.slice.value, int))


def _positional_reads(fn: ast.AST, shared: set[str]) -> list[tuple[int, str]]:
    """`(line, sql name)` of every positional read of a shared query's result in `fn`."""
    results: dict[str, str] = {}   # variable -> sql name
    rows: dict[str, str] = {}      # loop variable over a result -> sql name
    hits: list[tuple[int, str]] = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            sql = _shared_query(n.value, shared)
            if sql and isinstance(n.targets[0], ast.Name):
                results[n.targets[0].id] = sql
            elif sql and isinstance(n.targets[0], ast.Tuple):
                hits.append((n.lineno, sql))
    for n in ast.walk(fn):
        if isinstance(n, (ast.For, ast.comprehension)):
            it = n.iter
            src = results.get(it.id) if isinstance(it, ast.Name) else _shared_query(it, shared)
            if src and isinstance(n.target, ast.Name):
                rows[n.target.id] = src
            elif src and isinstance(n.target, ast.Tuple):
                hits.append((getattr(n.target, "lineno", 0), src))
    for n in ast.walk(fn):
        if _is_int_subscript(n):
            v = n.value
            while _is_int_subscript(v):
                v = v.value
            sql = (_shared_query(v, shared)
                   or (results.get(v.id) or rows.get(v.id) if isinstance(v, ast.Name) else None))
            if sql:
                hits.append((n.lineno, sql))
        elif (isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", ""))
              == "DataFrame" and n.args and any(k.arg == "columns" for k in n.keywords)):
            a = n.args[0]
            sql = (results.get(a.id) if isinstance(a, ast.Name) else _shared_query(a, shared))
            if sql:
                hits.append((n.lineno, sql))
        elif isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Tuple):
            v = n.value.body if isinstance(n.value, ast.IfExp) else n.value
            if isinstance(v, ast.Name) and v.id in rows:
                hits.append((n.lineno, rows[v.id]))
    return hits


def positional_readers(source: str, module: str) -> set[tuple[str, int]]:
    """`(sql name, line)` of each positional read of a cross-module query. Pure."""
    tree = ast.parse(source)
    shared = _imported_elsewhere(tree, module)
    found: set[tuple[str, int]] = set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.update((sql, line) for line, sql in _positional_reads(fn, shared))
    return found


def _scan() -> dict[tuple[str, str], list[int]]:
    out: dict[tuple[str, str], list[int]] = {}
    for scope in _SCOPES:
        for path in sorted((ROOT / scope).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            module = rel[:-3].replace("/", ".")
            try:
                found = positional_readers(path.read_text(encoding="utf-8"), module)
            except SyntaxError:
                continue
            for sql, line in found:
                out.setdefault((rel, sql), []).append(line)
    return out


def test_no_new_consumer_reads_a_shared_query_by_position() -> None:
    """LE GARDE. A positional read of another module's query, not already on the list."""
    found = _scan()
    new = {k: sorted(v) for k, v in found.items() if k not in _KNOWN}
    assert not new, (
        f"positional read(s) of a query defined in ANOTHER module: {new}.\n"
        "When that module adds or reorders a column, this consumer reads the wrong one "
        "without failing — R369: the MRR showed the artist count. Use `db.fetch_df(...)` "
        "and read the columns by name.")


def test_the_known_list_is_not_stale() -> None:
    """A site fixed (read by name) must leave the list — otherwise the list lies."""
    gone = sorted(set(_KNOWN) - set(_scan()))
    assert not gone, f"no longer positional, remove from `_KNOWN`: {gone}"


_PRE_FIX_BILLING = '''
def _show_admin_view(db):
    from src.utils.mrr import MRR_LABEL, mrr_by_plan_sql, mrr_params
    rev_rows = db.fetch_query(mrr_by_plan_sql(), mrr_params())
    if rev_rows:
        total_mrr = sum(float(r[2] or 0) for r in rev_rows)
        df_mrr = pd.DataFrame(rev_rows, columns=["Plan", "Artistes", "MRR"])
'''
_PRE_FIX_ADMIN = '''
def _render_supervision(db):
    from src.utils.mrr import MRR_LABEL, mrr_by_plan_sql, mrr_params
    rev = db.fetch_query(mrr_by_plan_sql(), mrr_params())
    mrr = sum(float(r[2] or 0) for r in rev) if rev else 0.0
'''


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """AUTO-PROOF, both directions (rule 20), on synthetic code."""
    # The two live sites it was admitted on, written as they were before R369.
    assert positional_readers(_PRE_FIX_BILLING, "src.dashboard.views.billing")
    assert positional_readers(_PRE_FIX_ADMIN, "src.dashboard.views.admin")
    # False negative: the defect written another way — a direct tuple unpack.
    other = "from src.x import OTHER_SQL\ndef f(db):\n    a, b = db.fetch_query(OTHER_SQL)[0]\n"
    assert positional_readers(other, "src.y"), "a direct unpack of a shared query is missed"
    # False positive 1: a SAME-module constant (gold_invariants DUPLICATE_SQL shape).
    local = ("DUPLICATE_SQL = 'SELECT a, b'\n"
             "def f(db):\n    return [r[0] for r in db.fetch_query(DUPLICATE_SQL)]\n")
    assert not positional_readers(local, "src.utils.gold_invariants")
    # False positive 2: a by-name consumer of a shared query (treasury_chart shape).
    by_name = ("from src.utils.mrr import mrr_by_plan_sql\n"
               "def f(db):\n    df = db.fetch_df(mrr_by_plan_sql())\n    return df['mrr'][0]\n")
    assert not positional_readers(by_name, "src.y")


def test_the_scan_is_not_vacuous() -> None:
    """The scan must reach real sites — a walker that sees nothing is green for nothing."""
    assert len(_scan()) >= len(_KNOWN) > 0
