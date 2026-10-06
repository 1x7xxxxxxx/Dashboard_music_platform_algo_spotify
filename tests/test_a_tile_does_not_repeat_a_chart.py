"""R258 (critic f) — a tile does not repeat a chart of its own page, unreviewed.

Type: Test
Uses: tools/dev/gold_coverage.py (collect_surfaces — the sources of every tile and figure)

Owner (notes L549, « aucune redondance ») : a tile that restates a figure beside it is
the same number twice. The FINGERPRINT here is (page, sources read) shared by a tile and a
figure: the measure of a tile is not readable from its code the way a figure's `y=` is, so
a shared fingerprint is a CANDIDATE, reviewed site by site and recorded below with its
verdict (rule 20 : a form is not the property). A new candidate fails until reviewed.

Measured 2026-09-28 : 162 tiles, 5 shared (page, sources) groups, 0 real repeats — each
tile shows a number the figure does not display (an indexed chart, another population, a
per-DAG facet) or another measure.

Mutation record (2026-09-28) : one reviewed entry removed → red ; a synthetic tile added
beside a figure on the same source → the detector sees it (non-vacuity test).
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "dev"))

# (page file, tile label key) → why it is not the chart's number.
REVIEWED: dict[tuple[str, str], str] = {
    ("src/dashboard/views/home_tiles.py", "home.tile_meta"):
        "R423: ad spend in €; the donut splits streams by platform",
    ("src/dashboard/views/home_tiles.py", "home.tile_hypeddit"):
        "R423: a click-through rate; the donut splits streams by platform",
    ("src/dashboard/views/home_tiles.py", "home.tile_shazam"):
        "R423: Shazam counts are not streams; the donut does not draw them",
    ("src/dashboard/views/home_tiles.py", "📸 Instagram"):
        "R423: a follower headcount, not in the stream total the donut splits",
    ("src/dashboard/views/etl_logs.py", "etl_logs.kpi_runs"):
        "total over every DAG; the chart facets runs per DAG and per day",
    ("src/dashboard/views/etl_logs.py", "etl_logs.kpi_success_rate"):
        "a rate the chart does not draw",
    ("src/dashboard/views/etl_logs.py", "etl_logs.kpi_avg_duration"):
        "a duration; the chart counts runs",
    ("src/dashboard/views/etl_logs.py", "etl_logs.kpi_failed_runs"):
        "total over every DAG; the chart facets runs per DAG and per day",
    ("src/dashboard/views/meta_x_spotify.py", "meta_x_spotify.tile_spend"):
        "absolute €; the chart is indexed (base 100) and shows no absolute value",
    ("src/dashboard/views/meta_x_spotify.py", "meta_x_spotify.tile_streams"):
        "absolute streams; the chart is indexed (base 100)",
    ("src/dashboard/views/meta_x_spotify.py", "meta_x_spotify.tile_cost_per_stream"):
        "a ratio the chart does not draw",
    ("src/dashboard/views/meta_x_spotify.py", "meta_x_spotify.tile_conversion"):
        "a ratio the chart does not draw",
    ("src/dashboard/views/revenue_forecast.py", "ARPU"):
        "ARPU per user; the chart is MRR per plan",
    ("src/dashboard/views/revenue_forecast.py", "revenue_forecast.ltv_global"):
        "a lifetime value; the chart is MRR per plan",
    ("src/dashboard/views/trigger_algo/_tab_catalogue.py", "trigger_algo.cat.tile_closest"):
        "the closest track of the WHOLE catalogue; the gauges show the 5 selected",
    ("src/dashboard/views/trigger_algo/_tab_catalogue.py", "trigger_algo.cat.tile_progress"):
        "the progress of that catalogue-wide track, on its one lever",
    ("src/dashboard/views/trigger_algo/_tab_lifecycle.py", "trigger_algo.lifecycle.age_metric"):
        "the track's age; the curves are the cohort, the age is only a dashed mark",
}


def candidates(surfaces) -> set[tuple[str, str]]:
    """(page, tile label) of every tile sharing its sources with a figure of its page."""
    groups = collections.defaultdict(lambda: {"figure": [], "tuile": []})
    for s in surfaces:
        src = tuple(sorted(n for _, n in s.sl.sources))
        if src and s.kind in ("figure", "tuile"):
            groups[(s.rel, src)][s.kind].append(s)
    return {(rel, t.what) for (rel, _), g in groups.items() if g["figure"]
            for t in g["tuile"]}


def _surfaces():
    import gold_coverage as gc
    gold, known = gc.scan_sql()
    files = gc.load_python()
    slicer = gc.Slicer(files, gc.build_call_index(files), gold, known, gc.sql_wrappers(files))
    return gc.collect_surfaces(files, slicer)


def test_every_tile_sharing_a_charts_sources_was_reviewed():
    found = candidates(_surfaces())
    new = sorted(found - set(REVIEWED))
    assert not new, (f"tuile(s) qui lisent les mêmes sources qu'un graphique de leur page, "
                     f"non revues : {new} — retirer la tuile si elle répète le graphique, "
                     "sinon l'inscrire dans REVIEWED avec la raison")
    assert found, "no candidate at all — the scan no longer reads the pages"


def test_the_detector_sees_a_tile_beside_its_chart_not_vacuous():
    class S:
        def __init__(self, kind, what, src):
            self.kind, self.rel, self.what = kind, "p.py", what
            self.sl = type("Sl", (), {"sources": {("table", src)}})()
    got = candidates([S("figure", "plotly_chart", "t"), S("tuile", "p.total", "t"),
                      S("tuile", "p.other", "u")])
    assert got == {("p.py", "p.total")}
