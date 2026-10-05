"""R271 (owner note L8) — the recap page lists the review's best charts, generated, routed,
and never redrawn.

Type: Test
Uses: tools/dev/build_recap.py, src/dashboard/content/recap_charts.py, src/dashboard/routes.py

Mutation record (2026-09-28) : `ranked` keeping a chart graded « corriger » → red ; a
recap entry pointing at an unrouted page → red ; the generated file edited by hand →
the staleness check went red.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_recap", ROOT / "tools/dev/build_recap.py")
br = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(br)


def test_only_kept_routed_charts_rank_best_first_without_plumbing():
    review = {
        "src/dashboard/views/a.py::f#1": {"q": "Question A ? (fusion R212)", "role": "meta",
                                          "d": 5, "c": 5, "p": 5, "v": "garder"},
        "src/dashboard/views/b.py::f#1": {"q": "Question B ?", "role": "meta",
                                          "d": 5, "c": 5, "p": 5, "v": "corriger"},
        "src/dashboard/views/c.py::f#1": {"q": "Question C ?", "role": "archi",
                                          "d": 5, "c": 5, "p": 5, "v": "garder"},
        "src/dashboard/views/z.py::f#1": {"q": "Question Z ?", "role": "meta",
                                          "d": 1, "c": 1, "p": 1, "v": "garder"},
        "pdf:roi": {"q": "PDF", "role": "business", "d": 5, "c": 5, "p": 5, "v": "garder"},
    }
    routes = {"pa": "views.a", "pb": "views.b", "pc": "views.c"}
    assert br.ranked(review, routes) == [("Question A ?", "pa", 15)]


def test_every_recap_entry_opens_a_routed_page_not_vacuous():
    from src.dashboard.content.recap_charts import RECAP
    from src.dashboard.routes import ROUTES
    assert len(RECAP) >= 5
    assert all(page in ROUTES for _q, page, _s in RECAP)


def test_the_generated_recap_matches_the_review():
    r = subprocess.run([sys.executable, str(ROOT / "tools/dev/build_recap.py"), "--check"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
