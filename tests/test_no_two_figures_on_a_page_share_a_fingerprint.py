"""No two figures of one page plot the same measure from the same sources.

Type: Test
Uses: tools/dev/charts_dossier/inventory.py (sites, measure_of)
Depends on: tools/dev/gold_coverage.py (sources of every figure)
Persists in: nothing

R207 (2026-09-27). The owner, after reviewing the charts dossier: « une méthode pour ne plus
créer de doublons ». The dossier had them — a cumulative curve beside the flow it summed
(db_health), a map beside the per-country chart of the same spend (meta_breakdowns).

THE FINGERPRINT has three axes, and the third is the one that makes it a detector:
(page file, sources read, measure plotted). Sources alone matched 24 sites on 8 pages that
plot DIFFERENT things (code-critic, 2026-09-27) — a guard built on them would have been a
register of exemptions. The measure is read from the CODE (the `x=`/`y=`/`values=`…
arguments of the figure behind each render call), never from the review's prose: two
questions can be worded apart for one measure, and a textual guard is blind.

A twin that is on purpose goes in `DECLARED_TWINS` with its reason. Measured when written:
0 pairs on 84 figures (70 with a measure read).
"""
from __future__ import annotations

import ast
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "dev" / "charts_dossier"))

from inventory import measure_of, sites  # noqa: E402

# (key, key) → why these two figures may share a fingerprint.
DECLARED_TWINS: dict[tuple[str, str], str] = {}


def _twins(entries) -> list[list[str]]:
    groups = collections.defaultdict(list)
    for e in entries:
        if e["kind"] == "figure" and e["measure"] and e["sources"]:
            groups[(e["site"].split(":")[0], tuple(e["sources"]),
                    tuple(e["measure"]))].append(e["key"])
    return [sorted(v) for v in groups.values() if len(v) > 1]


def test_no_page_draws_the_same_measure_twice() -> None:
    undeclared = [pair for pair in _twins(sites())
                  if tuple(pair[:2]) not in DECLARED_TWINS]
    assert not undeclared, (
        "two figures of one page read the same sources and plot the same measure: "
        f"{undeclared}. Merge them, or declare the pair in DECLARED_TWINS with the reason.")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: two figures of one function plotting `spend` by `week` are twins."""
    code = (
        "def show(df):\n"
        "    fig = px.bar(df, x='week', y='spend')\n"
        "    st.plotly_chart(fig)\n"
        "    fig2 = go.Figure(go.Scatter(x=df['week'], y=df['spend']))\n"
        "    st.plotly_chart(fig2)\n")
    tree = ast.parse(code)
    a, b = measure_of(tree, 3), measure_of(tree, 5)
    assert a == b == ("spend", "week"), (a, b)
    entries = [{"kind": "figure", "site": "v.py:3", "key": "v.py::show#1",
                "sources": ["t"], "measure": list(a)},
               {"kind": "figure", "site": "v.py:5", "key": "v.py::show#2",
                "sources": ["t"], "measure": list(b)}]
    assert _twins(entries) == [["v.py::show#1", "v.py::show#2"]]


def test_a_different_measure_or_helper_is_not_a_twin() -> None:
    code = (
        "def show(df):\n"
        "    fig = px.bar(df, x='week', y='spend')\n"
        "    st.plotly_chart(fig)\n"
        "    st.plotly_chart(px.line(df, x='week', y='clicks'))\n"
        "    st.plotly_chart(_cumulative(df))\n")
    tree = ast.parse(code)
    assert len({measure_of(tree, 3), measure_of(tree, 4), measure_of(tree, 5)}) == 3


def test_the_review_triage_shows_the_same_twins() -> None:
    """The owner sees a probable twin at review time, with its fiche numbers."""
    from triage import likely_twins, render
    inv = [{"kind": "figure", "site": "v.py:3", "key": "a", "sources": ["t"], "measure": ["y"]},
           {"kind": "figure", "site": "v.py:9", "key": "b", "sources": ["t"], "measure": ["y"]},
           {"kind": "figure", "site": "w.py:9", "key": "c", "sources": ["t"], "measure": ["y"]}]
    twins = likely_twins(inv, {"a": 4, "b": 7})
    assert twins == [["a", "b"]]
    assert "fiche 4 (a) ↔ fiche 7 (b)" in render([], twins, {"a": 4, "b": 7})
