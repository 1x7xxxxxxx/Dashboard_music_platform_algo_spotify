"""The age finding is on the free breakdowns, computed once with the Premium score (R409).

Type: Guard
Uses: src.dashboard.utils.age_brackets, src.dashboard.views.meta_breakdowns,
  src.dashboard.views.meta_cpr_optimizer
Depends on: nothing (pure functions, source text of two views)
Persists in: nothing

Mutations, 2026-10-05: `_render_age_finding(df)` call removed from `_render_frames` → RED;
`_affinite_age` aggregating its own brackets instead of `brackets` → RED.

Owner, 2026-10-05: « la tranche d'âge va dans la vue croisée free, ce sont des données
déjà accessibles sur Meta Ads ». Two properties: the finding is drawn by the free
section and no longer by the Premium page, and both read ONE bracket computation —
two would let the free page call a bracket cheapest that the score does not reward.
"""
from __future__ import annotations

import ast
import inspect

import pandas as pd

_ROWS = pd.DataFrame({
    "age_range": ["18-24", "25-34", "35-44", "Unknown", "18-24"],
    "spend": [100.0, 60.0, 40.0, 0.0, 20.0],
    "results": [800, 1000, 200, 7, 400],
})


def test_a_bracket_without_spend_has_no_cpr_and_the_cheapest_is_named() -> None:
    from src.dashboard.utils.age_brackets import brackets, finding

    par = brackets(_ROWS)
    unknown = par.set_index("age_range").loc["Unknown"]
    assert pd.isna(unknown["cpr"]), "a bracket with 0 € spend was given a CPR"
    f = finding(par)
    assert (f["best"], f["worst"]) == ("25-34", "35-44")
    assert f["cb"] == 60.0 / 1000 and f["cw"] == 40.0 / 200
    # 18-24 (0,1 €) is the median: only 35-44 is worse — 40 € of 220 €.
    assert round(f["part"], 1) == round(40 / 220 * 100, 1)
    assert finding(brackets(_ROWS[_ROWS["age_range"] == "25-34"])) is None


def _called_names(module) -> set[str]:
    """Every function NAME called in a module's code — comments and strings excluded."""
    tree = ast.parse(inspect.getsource(module))
    return {n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
            for n in ast.walk(tree) if isinstance(n, ast.Call)}


def _defined(module) -> set[str]:
    return {n.name for n in ast.walk(ast.parse(inspect.getsource(module)))
            if isinstance(n, ast.FunctionDef)}


def test_the_free_section_draws_it_and_the_premium_page_does_not() -> None:
    from src.dashboard.views import meta_breakdowns, meta_cpr_optimizer

    assert "_render_age_finding" in _called_names(meta_breakdowns)
    assert "finding" in _called_names(meta_breakdowns)
    assert "finding" not in _called_names(meta_cpr_optimizer)
    assert not {d for d in _defined(meta_cpr_optimizer) if "age_panel" in d}, (
        "the age finding is still drawn behind the Premium gate")


def test_the_score_reads_the_same_brackets(monkeypatch) -> None:
    from src.dashboard.utils import age_brackets
    from src.dashboard.views import meta_cpr_optimizer

    calls = []
    real = age_brackets.brackets
    monkeypatch.setattr(age_brackets, "brackets", lambda rows: calls.append(1) or real(rows))

    class _Db:
        def fetch_df(self, _sql, _params):
            return _ROWS.assign(campaign_name=["A", "A", "B", "B", "B"])

    affinite, par = meta_cpr_optimizer._affinite_age(_Db(), 1, "", ())
    assert calls, "the score computes its own brackets"
    assert affinite["A"] > 1 > affinite["B"], affinite
