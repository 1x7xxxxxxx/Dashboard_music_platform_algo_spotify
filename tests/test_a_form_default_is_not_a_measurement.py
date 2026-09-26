"""A form field nobody filled is written as NULL, never as its widget default.

Type: Test
Uses: streamlit.testing.v1.AppTest, ast, information_schema (live Postgres, one test)
Depends on: src/dashboard/views/data_wrapped.py (`_render_wrapped_body`,
            `_upsert_wrapped`), every `st.number_input` under src/dashboard/,
            .claude/skills/dashboard-view/SKILL.md (Pitfall 10)
Persists in: nothing — the form writes into a fake handler

Why this guard exists
---------------------
Measured on 2026-09-26, `artist_wrapped` row (artist 1, 2025): saves 0, playlist adds
0, the four `*_gain_pct` at 0.00, top_fans_count 0, top_fans_rank 5 — written seven
minutes after the 2024 row (5 210 saves, +475 %, 11 fans). Every field of the Wrapped
form was built with `value=int(g(col) or 0)` (rank: `or 5`) and the save wrote every
widget value, so a field left empty went into the base as a measurement. The charts
already `dropna()`; a stored 0 is not NA, so they drew +0.0 % where the volumes say
-84 %. `hypeddit.py` met the same form default on 2026-09-21.

What it holds, reading the WRITTEN ROW (never the source text):

  1. filling only listeners and streams writes those two and NULL for the ten others;
  2. a 0 TYPED by the user stays 0 — the fix must not erase real zeros;
  3. a form with nothing filled writes nothing;
  4. structurally, over every `st.number_input` of the dashboard: no `value=` falls
     back with `or <number>` on a column the SCHEMA declares NULLABLE. The allowlist
     is not a list in this file: it is `information_schema.columns.is_nullable`, so a
     new NOT NULL column is exempt and a new NULLABLE one is guarded without anyone
     editing this test;
  5. the `dashboard-view` skill example, EXECUTED, keeps a NULL counter as NaN — the
     example every new chart is copied from taught `.fillna(0)`.

Class: `a-form-default-persisted-as-a-measurement`
(family `un-nombre-affirmé-qui-n-a-pas-été-mesuré`).
"""
from __future__ import annotations

import ast
import pathlib
import re

from tests.db_gate import requires_live_db

_ROOT = pathlib.Path(__file__).resolve().parent.parent

# The order `_upsert_wrapped` binds its payload in — read from its SQL, see below.
_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import pandas as pd
import streamlit as st
from src.dashboard.views import data_wrapped as dw


class _FakeDb:
    def fetch_df(self, query, params=None):
        return pd.DataFrame()          # no existing row: every field starts empty

    def fetch_query(self, query, params=None):
        return []

    def execute_query(self, query, params=None):
        st.session_state.setdefault("writes", []).append(params)


_original = dw._tab_charts                       # AppTest shares sys.modules with the tests:
dw._tab_charts = lambda artist_options: None     # the charts are not under test — and the
try:                                             # patch must not leak into later tests
    dw._render_wrapped_body(_FakeDb(), {{"A": 1}})
finally:
    dw._tab_charts = _original
"""

_COLUMNS = ("listeners", "streams", "hours_listened", "countries",
            "listener_gain_pct", "stream_gain_pct", "save_gain_pct",
            "playlist_add_gain_pct", "saves", "playlist_adds",
            "top_fans_count", "top_fans_rank")


def _app():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=str(_ROOT)))
    at.run(timeout=60)
    assert not at.exception, [e.value for e in at.exception]
    return at


def _field(at, *labels: str):
    """The form's number_input whose label is one of `labels` (FR default or EN)."""
    for w in at.number_input:
        if w.label in labels:
            return w
    raise AssertionError(f"no number_input labelled {labels}; seen "
                         f"{[w.label for w in at.number_input]}")


def _save(at):
    btn = next((b for b in at.button if "Enregistrer" in b.label or "Save" in b.label),
               None)
    assert btn is not None, [b.label for b in at.button]
    btn.click().run(timeout=60)
    return list(at.session_state["writes"]) if "writes" in at.session_state else []


def _written_row(params) -> dict:
    """(artist_id, year, <12 values>) → {column: value}, in `_upsert_wrapped`'s order."""
    from src.dashboard.views import data_wrapped as dw
    import inspect

    src = inspect.getsource(dw._upsert_wrapped)
    order = re.findall(r"values\['(\w+)'\]", src)
    assert sorted(order) == sorted(_COLUMNS), order
    return dict(zip(order, params[2:]))


def test_an_empty_field_is_written_as_null() -> None:
    at = _app()
    _field(at, "Listeners").set_value(5100)
    _field(at, "Streams totaux", "Total streams").set_value(16700)
    writes = _save(at)
    assert len(writes) == 1, f"one save, one write — got {writes}"
    row = _written_row(writes[0])
    assert row["listeners"] == 5100 and row["streams"] == 16700, row
    left_empty = {c: v for c, v in row.items()
                  if c not in ("listeners", "streams") and v is not None}
    assert not left_empty, (
        f"fields nobody filled were written as measurements: {left_empty}. On "
        "2026-09-26 the 2025 Wrapped row held saves 0, the four gains at 0.00, "
        "top_fans_count 0 and top_fans_rank 5 (the widget default) this way.")


def test_a_typed_zero_stays_zero() -> None:
    at = _app()
    _field(at, "Saves").set_value(0)
    _field(at, "Gain streams (%)", "Streams gain (%)").set_value(0.0)
    row = _written_row(_save(at)[0])
    assert row["saves"] == 0 and row["stream_gain_pct"] == 0.0, (
        f"a 0 the artist TYPED must reach the base as 0, got {row}: the fix keeps the "
        "distinction, it does not erase real zeros")
    assert row["listeners"] is None, row


def test_an_empty_form_writes_nothing() -> None:
    at = _app()
    assert _save(at) == [], "a form with no field filled must not write a row"
    assert any("Rien à enregistrer" in w.value or "Nothing to save" in w.value
               for w in at.warning), [w.value for w in at.warning]


# ── 4. Structural, with the allowlist taken from the SCHEMA ─────────────────────

def defaults_on_nullable_columns(source: str, nullable: set[str]) -> list[tuple[int, str]]:
    """(line, column) of `number_input(value=<… '<col>' … or <number>>)` where <col>
    is NULLABLE. Pure: `nullable` is the set of column names the schema allows NULL in.

    The predicate is the PROPERTY, not a spelling: a prefill that reads a column by
    its string name and falls back on a number. Comments and docstrings are not AST,
    so prose about the defect cannot trip it."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "attr", getattr(node.func, "id", "")) == "number_input"):
            continue
        for kw in node.keywords:
            if kw.arg != "value":
                continue
            for sub in ast.walk(kw.value):
                if not (isinstance(sub, ast.BoolOp) and isinstance(sub.op, ast.Or)):
                    continue
                if not (isinstance(sub.values[-1], ast.Constant)
                        and isinstance(sub.values[-1].value, (int, float))):
                    continue
                cols = {c.value for v in sub.values[:-1] for c in ast.walk(v)
                        if isinstance(c, ast.Constant) and isinstance(c.value, str)}
                out += [(node.lineno, c) for c in sorted(cols & nullable)]
    return out


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity, both directions (rule 20): the defect's own spelling is caught; the
    fix, a NOT NULL column, and an `or` outside `value=` are not."""
    bad = "st.number_input('Saves', min_value=0, value=int(g('saves') or 0))\n"
    assert defaults_on_nullable_columns(bad, {"saves"}) == [(1, "saves")]
    rank = "st.number_input('R', min_value=1, value=int(row.get('top_fans_rank') or 5))\n"
    assert defaults_on_nullable_columns(rank, {"top_fans_rank"}) == [(1, "top_fans_rank")]
    fixed = "st.number_input('Saves', min_value=0, value=_prefill(g('saves'), int))\n"
    assert defaults_on_nullable_columns(fixed, {"saves"}) == []
    required = "st.number_input('N', value=int(g('song_count') or 0))\n"
    assert defaults_on_nullable_columns(required, {"saves"}) == [], (
        "a NOT NULL column is exempt: the schema says a value is required")
    elsewhere = "x = int(g('saves') or 0)\nst.number_input('S', value=x)\n"
    assert defaults_on_nullable_columns(elsewhere, {"saves"}) == []


@requires_live_db()
def test_no_form_prefills_a_nullable_column_with_a_number() -> None:
    import psycopg2

    from tests.db_gate import dsn

    conn = psycopg2.connect(**dsn())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name, bool_or(is_nullable = 'YES') "
                        "FROM information_schema.columns WHERE table_schema = 'public' "
                        "GROUP BY 1")
            rows = cur.fetchall()
    finally:
        conn.close()
    nullable = {c for c, n in rows if n}
    assert {"saves", "top_fans_rank", "stream_gain_pct"} <= nullable, (
        "the schema no longer reads as expected — the check below would be vacuous")
    hits = []
    for path in sorted((_ROOT / "src" / "dashboard").rglob("*.py")):
        rel = path.relative_to(_ROOT)
        hits += [f"{rel}:{ln} ({col})"
                 for ln, col in defaults_on_nullable_columns(path.read_text(), nullable)]
    assert not hits, (
        f"a form field falls back on a number for a NULLABLE column: {hits}. Once "
        "saved, that default is indistinguishable from a measurement — prefill with "
        "None (Streamlit renders an empty field) and write None when it stays empty.")


# ── 5. The skill example every new chart is copied from ─────────────────────────

def test_the_skill_example_keeps_a_null_counter_as_nan() -> None:
    import pandas as pd

    text = (_ROOT / ".claude/skills/dashboard-view/SKILL.md").read_text(encoding="utf-8")
    section = text[text.index("### 10."):text.index("### 11.")]
    code = re.search(r"```python\n(.*?)```", section, re.S).group(1)
    df = pd.DataFrame({"likes_count": [None, 5], "playback_count": [10, 50]},
                      dtype=object)
    scope = {"pd": pd, "df": df}
    exec(code, scope)  # noqa: S102 — the example is ours, executing it is the point
    assert pd.isna(scope["likes"].iloc[0]), (
        f"the skill example turns a NULL counter into {scope['likes'].iloc[0]!r}; a "
        "chart copied from it draws that as a measured 0")
    assert pd.isna(df["eng_rate"].iloc[0]) and df["eng_rate"].iloc[1] == 10.0, df
