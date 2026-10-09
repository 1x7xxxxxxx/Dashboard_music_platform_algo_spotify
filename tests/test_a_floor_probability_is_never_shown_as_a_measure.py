"""A probability on the calibration floor is never shown — nor ranked — as a measure.

Type: Hook (guard)
Uses: src.dashboard.utils.algo_preview_data (sur_le_plancher, proba_affichable, format_proba),
      src.utils.ml_inference._calibrate, every surface that displays an ML probability
Depends on: machine_learning/models/*/calibration.json (read through `_calibrate`); no DB
Persists in: nothing

Measured 2026-09-26 on the local `spotify_etl`: the latest prediction of every song in
`ml_song_predictions` (11 rows, 33 probabilities) — **33 of 33 on the calibration floor**
(raw score <= 0.05; at raw 0 the floor is DW 6.53 %, RR 6.51 %, Radio 10.72 %). The PDF
chart of « Ô Chiotte l'arbitre » rendered exactly ['STOP', 'SCALER', '7%', '7%', '11%'].
The floor rule lived in two views (one refused the number, one marked it « ≈ plancher »)
and eleven other surfaces printed it as a distinguishing percentage, or ranked on it.

The fix is ONE door, `proba_affichable` / `format_proba`, policy REFUSE. This file holds:

  (a) BEHAVIOUR — every surface's formatter, fed a floor row, prints no `\\d+ ?%`; fed an
      off-floor row, still prints it (so the test cannot pass by suppressing all).
      The floor fixture is DERIVED at test time from the running calibration
      (`_calibrate(algo, 0.0)` — raw score 0 is on the floor by definition), never a
      literal copied from today's snapshot: a recalibration cannot make it vacuous.
  (b) SCORE — the CPR optimizer's score does not move with the floor-driven max.
  (c) RATCHET — every module under src/ and airflow/dags/ whose SQL reads a
      `*_probability` column goes through the door or is allowlisted with a reason;
      and inside such modules every percentage token must be bound to the door's
      output (taint check), so importing the door once and printing a second
      probability raw stays RED.

Class: `two-surfaces-two-truths` (family deux-surfaces-deux-nombres).
Not covered (named follow-ups): selection rules that argmax over floor values WITHOUT
displaying them — `period_side_metrics.best_algo_p`, `kpis.ml_top_song`; a probability
read from the API JSON by an external consumer; a future algo absent from
calibration.json (`sur_le_plancher` fails open → shown).
"""
from __future__ import annotations

import ast
import pathlib
import re

import pandas as pd
import pytest

from src.dashboard.utils.algo_preview_data import (
    PLANCHER_TEXTE, format_proba, proba_affichable, sur_le_plancher)

ROOT = pathlib.Path(__file__).resolve().parents[1]
PCT = re.compile(r"\d+(?:[.,]\d+)? ?%")
ALGOS = ("dw", "rr", "radio")


def _floor(algo: str) -> float:
    from src.utils.ml_inference import _calibrate

    p = _calibrate(algo, 0.0)
    assert p is not None and sur_le_plancher(algo, p), (
        f"{algo}: the calibration no longer puts raw 0 on the floor ({p}) — this "
        "fixture would be vacuous; re-derive what a floor value is")
    return p


FLOOR = {a: _floor(a) for a in ALGOS}
OFF = 0.60
assert not any(sur_le_plancher(a, OFF) for a in ALGOS), (
    "0.60 is on the floor under this calibration — the reciprocal fixture is vacuous")


def _no_pct(text: str, where: str) -> None:
    found = PCT.findall(text)
    assert not found, f"{where} prints a floor probability as a measure: {found} in {text!r}"


# ── (a) behaviour, surface by surface ────────────────────────────────────────

def test_the_door_refuses_the_floor_and_keeps_a_measure():
    for a in ALGOS:
        assert proba_affichable(a, FLOOR[a]) is None
        assert format_proba(a, FLOOR[a], floor_text=PLANCHER_TEXTE) == PLANCHER_TEXTE
    assert format_proba("dw", OFF) == "60%"
    assert format_proba("dw", None) == "—"
    assert format_proba("dw", float("nan")) == "—"


class _DB:
    def __init__(self, row):
        self.row = row

    def fetch_query(self, sql, params=None):
        return [self.row]


def _pdf_chart_texts(monkeypatch, row) -> list[str]:
    from matplotlib.axes import Axes

    from src.dashboard.utils import pdf_charts

    seen: list[str] = []
    real = Axes.text

    def spy(self, x, y, s, *a, **k):
        seen.append(str(s))
        return real(self, x, y, s, *a, **k)

    monkeypatch.setattr(Axes, "text", spy)
    assert pdf_charts.ml_probabilities(_DB(row), 1, "T") is not None
    return seen


def test_pdf_chart_ml_probabilities(monkeypatch):
    seen = _pdf_chart_texts(monkeypatch, (FLOOR["dw"], FLOOR["rr"], FLOOR["radio"]))
    _no_pct(" | ".join(seen), "pdf_charts.ml_probabilities")
    assert "STOP" not in seen and "SCALER" not in seen, (
        f"pdf_charts.ml_probabilities draws a STOP/SCALER verdict over three floors: {seen}")
    seen = _pdf_chart_texts(monkeypatch, (OFF, FLOOR["rr"], FLOOR["radio"]))
    assert "60%" in seen and "STOP" in seen, seen
    _no_pct(" | ".join(s for s in seen if s != "60%"), "pdf_charts.ml_probabilities")


def test_pdf_score20_cells():
    from src.dashboard.utils.pdf_exporter._renderers import _render_score20

    html = _render_score20([("T", None, "x", None, None,
                             FLOOR["dw"], FLOOR["rr"], FLOOR["radio"])])
    _no_pct(html, "_renderers._render_score20")
    html = _render_score20([("T", None, "x", None, None, OFF, FLOOR["rr"], FLOOR["radio"])])
    assert "60%" in html


def _cmp(early_dw, now_dw):
    base = {"n": 3, "as_of": None, "model_version": "v3"}
    return {"song": "T", "comparable": True, "reason": None,
            "early": {**base, "dw_probability": early_dw, "rr_probability": FLOOR["rr"],
                      "radio_probability": FLOOR["radio"]},
            "now": {**base, "dw_probability": now_dw, "rr_probability": FLOOR["rr"],
                    "radio_probability": FLOOR["radio"]}}


def test_pdf_trigger_then_now():
    from src.dashboard.utils.pdf_exporter._renderers import _render_trigger_then_now

    html = _render_trigger_then_now(_cmp(FLOOR["dw"], FLOOR["dw"]))
    _no_pct(html, "_renderers._render_trigger_then_now")
    assert "pts" not in html, "a delta between two floors is drawn as a movement"
    html = _render_trigger_then_now(_cmp(OFF, FLOOR["dw"]))
    assert "60%" in html and "pts" not in html, "no delta when EITHER endpoint is a floor"
    html = _render_trigger_then_now(_cmp(OFF, 0.70))
    assert "60%" in html and "70%" in html and "▲ 10 pts" in html


def test_pdf_prob_bar():
    from src.dashboard.utils.pdf_exporter._renderers import _prob_bar

    for a in ALGOS:
        _no_pct(_prob_bar(FLOOR[a], a), f"_renderers._prob_bar({a})")
        assert "prob-bar-wrap" not in _prob_bar(FLOOR[a], a), "a floor still draws a bar"
    assert "60%" in _prob_bar(OFF, "dw")


class _StrictPredictionsDB:
    """Raises, like Postgres, on a column `ml_song_predictions` does not have."""

    def __init__(self, row):
        from src.database.ml_schema import ML_SCHEMA  # the DDL is the truth
        ddl = ML_SCHEMA["ml_song_predictions"].split("CREATE INDEX")[0]
        self.cols = set(re.findall(r"^\s+([a-z_0-9]+)\s+[A-Z]", ddl, re.M))
        self.row = row

    def fetch_query(self, sql, params=None):
        if "ml_song_predictions" not in sql:
            return [(0,)]
        sel = re.search(r"SELECT(.*?)FROM", sql, re.S).group(1)
        for col in re.findall(r"[a-z_0-9]+", sel):
            if col not in self.cols:
                raise RuntimeError(f'column "{col}" does not exist')
        return [self.row]


def test_pdf_songs_focus_reads_real_columns_and_refuses_the_floor():
    import datetime as dt

    from src.dashboard.utils.pdf_exporter._collectors import _collect_songs_focus
    from src.dashboard.utils.pdf_exporter._renderers import _render_songs_focus

    db = _StrictPredictionsDB((FLOOR["dw"], FLOOR["rr"], FLOOR["radio"], 10, 5,
                               dt.date(2026, 9, 26)))
    assert "dw_probability" in db.cols, "the DDL reader is broken — vacuous fake"
    data = _collect_songs_focus(db, 1, ["T"], dt.date(2026, 9, 1), dt.date(2026, 9, 26))
    assert data[0]["ml"] is not None, (
        "the songs-focus SELECT names a column ml_song_predictions does not have — the "
        "except swallowed it and the ML block never renders")
    html = _render_songs_focus(data)
    cells = re.findall(r"<td>(.*?)</td>", html, re.S)
    _no_pct(" | ".join(cells[:3]), "_renderers._render_songs_focus")


def test_home_gate_tiles():
    """EXEMPTED by the owner on 2026-10-06 (R421): Home shows the raw predicted maximum,
    floor included — the floor caveat lives in the tile's tooltip. Pinned here so the
    exemption stays one surface wide and the format stays the number, not a label."""
    from src.dashboard.views.home_tiles import _format_gate

    for a in ALGOS:
        assert PCT.search(_format_gate(FLOOR[a])), "R421: the floor value is shown"
    assert _format_gate(OFF) == "60,0 %"
    assert _format_gate(None) == "—" and _format_gate(float("nan")) == "—"


def test_verdict_banner():
    from src.dashboard.views.trigger_algo._common._verdict import _verdict_message

    floor = {f"{a}_probability": FLOOR[a] for a in ALGOS}
    kind, text, algo, prob = _verdict_message(floor)
    assert kind == "floor" and algo is None and prob is None
    _no_pct(text, "_verdict._verdict_message")
    assert "STOP" not in text.split("—")[0] and "SCALER" not in text.split("—")[0]
    kind, text, algo, _p = _verdict_message({**floor, "dw_probability": OFF})
    assert kind == "scale" and algo == "DW" and "60%" in text
    # the argmax ignores floors: Radio's intercept (the highest floor) never wins
    kind, _t, algo, _p = _verdict_message({**floor, "rr_probability": 0.30})
    assert algo == "RR", "the argmax ran over a floor value"


def test_cpr_optimizer_labels():
    from src.dashboard.views.meta_cpr_optimizer import _ml_label

    _no_pct(_ml_label(FLOOR["dw"], FLOOR["rr"], FLOOR["radio"]), "meta_cpr_optimizer._ml_label")
    assert _ml_label(OFF, FLOOR["rr"], FLOOR["radio"]) == "60%"


def test_s4a_insight_bar_label():
    from src.dashboard.utils.s4a_entry_insight import _bar_label

    _no_pct(_bar_label(FLOOR["dw"], FLOOR["rr"], FLOOR["radio"]), "s4a_entry_insight._bar_label")
    assert _bar_label(OFF, FLOOR["rr"], FLOOR["radio"]) == "60%"
    # R442: a floor bar is unlabelled — the caption names the floor once.
    assert _bar_label(FLOOR["dw"], FLOOR["rr"], FLOOR["radio"]) == ""


def test_weekly_digest_top_candidate():
    from src.utils.digest_queries import ml_top_candidate

    assert ml_top_candidate([("A", FLOOR["dw"]), ("B", FLOOR["dw"] * 0.99)]) is None
    top = ml_top_candidate([("A", FLOOR["dw"]), ("B", OFF)])
    assert top == ("B", "60.0% probability")


def test_algos_tab_curve_leaves_gaps():
    from src.dashboard.views.trigger_algo._tab_algos import _proba_series

    assert _proba_series("radio", [FLOOR["radio"], OFF]) == [None, pytest.approx(60.0)]


# ── (b) the CPR SCORE, not its rendering ─────────────────────────────────────

def _campaigns(dw, rr, radio):
    return pd.DataFrame({
        "campaign_name": ["A", "B"], "track_name": ["a", "b"],
        "total_spend": [10.0, 10.0], "total_results": [100, 400],
        "cpr": [0.10, 0.20],
        "dw_prob": dw, "rr_prob": rr, "radio_prob": radio})


def test_cpr_score_is_unmoved_by_the_floor_driven_max():
    from src.dashboard.views.meta_cpr_optimizer import _compute_scores

    fl = FLOOR
    # two floor configurations: B's max floor (Radio) higher than A's in one, equal in
    # the other. With the ML factor in, the ratio of the two scores would change.
    s1 = _compute_scores(_campaigns([fl["dw"]] * 2, [fl["rr"]] * 2,
                                    [fl["dw"], fl["radio"]]), 0.15)
    s2 = _compute_scores(_campaigns([fl["dw"]] * 2, [fl["rr"]] * 2,
                                    [fl["radio"], fl["dw"]]), 0.15)
    assert list(s1["score_raw"]) == pytest.approx(list(s2["score_raw"])), (
        "the CPR score moved with which title's FLOOR is higher")
    assert s1.attrs["ml_in_score"] is False
    # neutral = the score with ML factor 1.0
    none = _compute_scores(_campaigns([None] * 2, [None] * 2, [None] * 2), 0.15)
    assert list(s1["score_raw"]) == pytest.approx(list(none["score_raw"]))
    # a MIXED set is neutral too: one real probability must not rank below neutrals
    mixed = _compute_scores(_campaigns([OFF, fl["dw"]], [fl["rr"]] * 2,
                                       [fl["radio"]] * 2), 0.15)
    assert list(mixed["score_raw"]) == pytest.approx(list(none["score_raw"]))
    # reciprocal: all off-floor ⇒ the ML factor DOES enter the score
    real = _compute_scores(_campaigns([0.9, OFF], [fl["rr"]] * 2, [fl["radio"]] * 2), 0.15)
    assert real.attrs["ml_in_score"] is True
    assert real["score_raw"].iloc[0] == pytest.approx(none["score_raw"].iloc[0] * 0.9)


# ── (c) the ratchet ──────────────────────────────────────────────────────────

_COL = re.compile(r"\b(dw|rr|radio)_probability\b")
_SQL = re.compile(r"\b(SELECT|FROM|INSERT|UPDATE)\b")
#: A column list that is not literal — `SELECT *` or `SELECT {cols}` — on the table that
#: holds the probabilities reads them too (`_loaders` and the CSV export read that way).
_OPAQUE = re.compile(r"SELECT\s+(\*|\{)[^;]*\bml_song_predictions\b", re.S)
_DOOR = {"proba_affichable", "format_proba", "texte_plancher"}

#: Modules whose SQL reads a *_probability column WITHOUT going through the door.
ALLOWED = {
    "src/api/routers/ml.py": "API JSON — raw value for machine consumers (guard_scope gap 1)",
    "src/api/routers/kpis.py": "API JSON; ml_top_song is a named follow-up",
    "src/dashboard/views/ml_performance.py": "admin model-monitoring page: the raw value IS the subject",
    "src/dashboard/utils/artist_cashflow.py": "aggregate expectations over a catalogue (cleared)",
    "src/dashboard/utils/period_side_metrics.py": "best_algo_p — selection follow-up, not displayed",
    "src/utils/trigger_rate_history.py": "loader: rendered by _renderers._render_trigger_then_now (door)",
    "src/dashboard/views/trigger_algo/_common/_loaders.py": "loader (SELECT {cols}): returns rows, formats nothing",
    "src/dashboard/utils/csv_exporter.py": "raw data export (SELECT *) for the tenant's own analysis, not a display",
    "src/dashboard/utils/pdf_exporter/_collectors.py": "loader: rendered by _renderers._prob_bar (door)",
    "src/utils/digest_queries.py": "SQL constant; its reader ml_top_candidate IS in the door",
}

#: Percentage tokens inside a door-bearing function that are NOT an ML probability.
#: Keyed by (module, function, exact source of the token) — never a whole function.
TOKEN_OK = {
    ("src/dashboard/views/revenue_forecast.py", "*", "p * 100"):
        "aggregate expectations (proba_moyenne), cleared",
}


def _modules() -> list[pathlib.Path]:
    return sorted([*ROOT.glob("src/**/*.py"), *ROOT.glob("airflow/dags/**/*.py")])


def _docstrings(tree) -> set[int]:
    ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = n.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant):
                ids.add(id(b[0].value))
    return ids


def _is_probability_sql(txt: str) -> bool:
    return bool((_COL.search(txt) and _SQL.search(txt)) or _OPAQUE.search(txt))


def _reads_probability_sql(tree) -> bool:
    """A SQL string constant (never a docstring or comment) that reads a probability."""
    doc = _docstrings(tree)
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc:
            if _is_probability_sql(n.value):
                return True
        if isinstance(n, ast.JoinedStr):
            txt = "".join(v.value if isinstance(v, ast.Constant) else "{x}"
                          for v in n.values)
            if _is_probability_sql(txt):
                return True
    return False


def _imports_door(tree) -> bool:
    """Imports a door name — or IS the door's module (defines one)."""
    return any((isinstance(n, ast.ImportFrom) and any(a.name in _DOOR for a in n.names))
               or (isinstance(n, ast.FunctionDef) and n.name in _DOOR)
               for n in ast.walk(tree))


def _call_name(n) -> str | None:
    if isinstance(n, ast.Call):
        f = n.func
        return f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute)
                                                     else None)
    return None


def _module_doors(tree) -> set[str]:
    """The door names, plus every module function that RETURNS a door value.

    A function that merely calls a door (a renderer that returns None) is not a
    door: its callers do not handle a probability.
    """
    doors = set(_DOOR)
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    changed = True
    while changed:
        changed = False
        for f in funcs:
            if f.name in doors:
                continue
            names = _tainted(f, doors)
            if any(isinstance(r, ast.Return) and r.value is not None
                   and _reaches(r.value, doors, names) for r in ast.walk(f)):
                doors.add(f.name)
                changed = True
    return doors


_COMPS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _bound(t) -> list[str]:
    """Names a target binds. `out[col] = …` binds `out`, never the index `col`."""
    if isinstance(t, ast.Name):
        return [t.id]
    if isinstance(t, (ast.Tuple, ast.List)):
        return [x for e in t.elts for x in _bound(e)]
    if isinstance(t, ast.Starred):
        return _bound(t.value)
    if isinstance(t, (ast.Subscript, ast.Attribute)):
        v = t.value
        while isinstance(v, (ast.Subscript, ast.Attribute)):
            v = v.value
        return [v.id] if isinstance(v, ast.Name) else []
    return []


def _comp_env(comp, env, doors, names) -> dict:
    env = dict(env)
    for gen in comp.generators:
        hit = _reaches(gen.iter, doors, names, env)
        for n in _bound(gen.target):
            env[n] = hit
    return env


def _reaches(expr, doors, names, env=None) -> bool:
    """Does `expr` carry a value that came out of the door?

    Scope-aware for comprehensions: `[f"{v:.0%}" for v in raw]` does not borrow the
    taint of another `v` bound elsewhere in the function from the door — the
    partial-usage mutation (door imported, a second probability printed raw) went
    GREEN through exactly that name collision before this was written.
    """
    env = env or {}
    if _call_name(expr) in doors:
        return True
    if isinstance(expr, ast.Name):
        return env[expr.id] if expr.id in env else expr.id in names
    if isinstance(expr, _COMPS):
        inner = _comp_env(expr, env, doors, names)
        parts = ([expr.key, expr.value] if isinstance(expr, ast.DictComp) else [expr.elt])
        parts += [c for g in expr.generators for c in g.ifs]
        return any(_reaches(x, doors, names, inner) for x in parts)
    return any(_reaches(c, doors, names, env) for c in ast.iter_child_nodes(expr))


def _tainted(fn, doors) -> set[str]:
    """Names bound in `fn` (outside comprehension targets) from a door value."""
    names: set[str] = set()
    changed = True
    while changed:
        before = len(names)
        for n in ast.walk(fn):
            pairs = []
            if isinstance(n, ast.Assign):
                pairs = [(t, n.value) for t in n.targets]
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign)) and n.value is not None:
                pairs = [(n.target, n.value)]
            elif isinstance(n, ast.NamedExpr):
                pairs = [(n.target, n.value)]
            elif isinstance(n, ast.For):
                pairs = [(n.target, n.iter)]
            for t, v in pairs:
                if _reaches(v, doors, names):
                    names.update(_bound(t))
        changed = len(names) != before
    return names


def _token_env(fn, node, doors, names) -> dict:
    """The comprehension bindings visible at `node`, outermost first."""
    parents = {c: p for p in ast.walk(fn) for c in ast.iter_child_nodes(p)}
    chain, cur = [], node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, _COMPS):
            chain.append(cur)
    env: dict = {}
    for comp in reversed(chain):
        env = _comp_env(comp, env, doors, names)
    return env


def _pct_tokens(fn):
    """(value expression, token node) for every percentage rendering in `fn`."""
    for n in ast.walk(fn):
        if isinstance(n, ast.JoinedStr):
            vals = n.values
            for i, v in enumerate(vals):
                if not isinstance(v, ast.FormattedValue):
                    continue
                spec = ast.unparse(v.format_spec) if v.format_spec else ""
                nxt = vals[i + 1] if i + 1 < len(vals) else None
                follows = (isinstance(nxt, ast.Constant) and isinstance(nxt.value, str)
                           and nxt.value.lstrip(" \u202f").startswith("%"))
                # a percent TYPE ends the spec (`.0%`); `%m/%Y` is a date format
                if spec.rstrip("'\"").endswith("%") or follows:
                    yield v.value, v
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
            for a, b in ((n.left, n.right), (n.right, n.left)):
                if isinstance(b, ast.Constant) and b.value in (100, 100.0):
                    yield a, n
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "format"):
            tpl = ast.unparse(n.func.value)
            if re.search(r"%\}|\}\s?%", tpl):
                for kw in n.keywords:
                    yield kw.value, kw.value


def _violations(rel: str, tree, src: str) -> list[str]:
    doors = _module_doors(tree)
    out = []
    for fn in tree.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        bearing = (_reads_probability_sql(fn)
                   or any(_call_name(c) in doors for c in ast.walk(fn)))
        if not bearing:
            continue
        names = _tainted(fn, doors)
        for value, node in _pct_tokens(fn):
            ok = _reaches(value, doors, names, _token_env(fn, node, doors, names))
            seg = ast.get_source_segment(src, node) or ast.unparse(node)
            if ok or (rel, "*", seg) in TOKEN_OK or (rel, fn.name, seg) in TOKEN_OK:
                continue
            out.append(f"{rel}:{node.lineno} {fn.name}: `{seg}`")
    return out


def _scan():
    flagged, bad = [], []
    for path in _modules():
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        if not _reads_probability_sql(tree):
            continue
        flagged.append(rel)
        if rel not in ALLOWED and not _imports_door(tree):
            bad.append(f"{rel}: reads *_probability in SQL, never imports the door")
        if rel not in ALLOWED:
            bad += _violations(rel, tree, src)
    return flagged, bad


def test_every_probability_reader_goes_through_the_door():
    flagged, bad = _scan()
    assert len(flagged) >= 12, (
        f"only {len(flagged)} modules found reading *_probability in SQL — the reader is "
        f"broken, the ratchet would pass vacuously: {flagged}")
    assert not bad, (
        "an ML probability reaches a display or a ranking without the floor door "
        "(`algo_preview_data.proba_affichable` / `format_proba`):\n  " + "\n  ".join(bad))


def test_the_allowlist_has_no_dead_entry():
    flagged, _bad = _scan()
    dead = sorted(set(ALLOWED) - set(flagged))
    assert not dead, f"allowlisted modules that no longer read the column: {dead}"
