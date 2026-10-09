"""The home page and the algo view price a release's trigger with ONE call (R372).

Type: Guard
Uses: src.dashboard.utils.algo_preview_data (budget_declenchement),
      src.dashboard.utils.period_side_metrics, src.dashboard.views.home_tiles
Depends on: live Postgres for the two DB tests (skipped without it)
Persists in: nothing

V5 (owner's screen review, 2026-10-05): the home's « Dernière sortie » block must name
the release, say it is the latest, and show the Meta budget that would buy its missing
streams — « la même fonction que la vue algo, pas une seconde formule ». Before R372 the
algo view priced the gap with its own parse of `features_json`, `_tab_budget_roi` had two
inline `cost_per_stream * seuil`, and the home's release came from the prediction table
while the measure layer named another title.

Critic decision recorded on the row: a CPR is € per Meta RESULT, not per stream, so « au
meilleur CPR » was dropped — the cost is the aggregate spend ÷ streams over the artist's
advertising span, labelled an order of magnitude.
"""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pytest

from tests.db_gate import db_ready

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src" / "dashboard" / "views"


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.func.id if isinstance(n.func, ast.Name) else n.func.attr
            for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, (ast.Name, ast.Attribute))}


def test_both_surfaces_call_the_shared_budget() -> None:
    # R421 (2026-10-06): the home's « 💰 Budget Meta pour déclencher » line is gone at the
    # owner's request; the two algo-view surfaces that still price a trigger remain.
    for path in (_VIEWS / "trigger_algo" / "_tab_reglages.py",
                 _VIEWS / "trigger_algo" / "_playlist_detail.py"):
        # R477 (2026-10-09): `_playlist_detail` now prices through `budget_fourchette`
        # — both names go through `budget_pour_streams`, the one formula.
        assert {"budget_declenchement", "budget_fourchette"} & _calls(path), (
            f"{path.name} no longer prices the trigger with budget_declenchement — a "
            "second formula will drift from the first")


def test_no_inline_cost_times_target_remains_in_the_algo_view() -> None:
    """`cost_per_stream * seuil` written by hand is the second formula R372 removed."""
    sites = []
    for path in (_VIEWS / "trigger_algo").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                names = {getattr(side, "id", None) for side in (node.left, node.right)}
                if names & {"cost_per_stream", "cout_par_stream"}:
                    sites.append(f"{path.name}:{node.lineno}")
    assert not sites, f"inline cost × streams outside budget_pour_streams: {sites}"


# R421 (2026-10-06): `test_a_budget_for_another_title_is_never_shown` retired with
# `home_tiles._release_budget_line`, the only renderer it guarded.


@pytest.mark.skipif(not db_ready(), reason="compares two surfaces on the live DB")
def test_the_home_and_the_algo_view_get_the_same_budget_for_the_release() -> None:
    from src.dashboard.utils import get_db_connection
    from src.dashboard.utils.algo_preview_data import budget_declenchement
    from src.dashboard.utils.period_side_metrics import period_side_metrics

    db = get_db_connection()
    try:
        latest = db.fetch_query(
            "SELECT song FROM v_s4a_song_measured_span WHERE artist_id = 1 "
            "AND first_streamed IS NOT NULL ORDER BY first_streamed DESC, song LIMIT 1")
        if not latest:
            pytest.skip("artist 1 has no measured release")
        home = budget_declenchement(db, 1)
        today = dt.date.today()
        side = period_side_metrics(db, 1, today - dt.timedelta(days=28), today)
        assert home["song"] == latest[0][0] == side["release_song"], (
            "the gates, the Shazam tile and the budget name different releases: "
            f"{home['song']!r} / {side['release_song']!r} / measured {latest[0][0]!r}")
        algo_view = budget_declenchement(db, 1, home["song"])
        assert algo_view == home, "the algo view prices the same title differently"
    finally:
        db.close()
