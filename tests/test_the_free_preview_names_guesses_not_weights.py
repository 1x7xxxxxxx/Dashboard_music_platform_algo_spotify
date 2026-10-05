"""The free algo preview lists the guessed criteria, never their SHAP weight (R410).

Type: Guard
Uses: src.dashboard.views.algo_preview, src.dashboard.views.trigger_algo._common._explain
Depends on: nothing (pure functions, AST of the preview, AppTest of one helper)
Persists in: nothing

Owner, 2026-10-05 (R406, point 2): yes to showing which values the model had to guess,
without the contributions — they are the Premium verdict. Two properties: the list is
the SAME one Premium warns about (one definition), and the free page calls nothing that
computes a contribution.

Mutations, 2026-10-05: `_render_guessed(view["guessed"])` removed from `show()` → RED;
`explain(...)` called inside `algo_preview.compose` → RED; a « (+0.3) » appended to each
rendered label → RED.
"""
from __future__ import annotations

import ast
import inspect

_SHAP_CALLS = {"explain", "shap_par_playlist", "_show_key_factors", "_show_lime_explanation",
               "_show_feature_importance"}


def test_a_criterion_entered_by_hand_is_not_a_guess() -> None:
    from src.dashboard.views.trigger_algo._common._explain import imputed_features

    cols = ["A", "NonAlgoStreams28Days_log", "HowManySongsDoYouHaveInRadioRightNow"]
    assert imputed_features({"NonAlgoStreams28Days_log": 0.0}, cols) == [
        "A", "HowManySongsDoYouHaveInRadioRightNow", "NonAlgoStreams28Days_log"]
    feats = {"A": 1.0, "NonAlgoStreams28Days_log": 0.0, "nonalgo_known": True,
             "HowManySongsDoYouHaveInRadioRightNow": 2.0}
    assert imputed_features(feats, cols) == []


def test_compose_carries_the_guesses_only_with_a_prediction() -> None:
    from src.dashboard.views.algo_preview import compose
    from src.utils.ml_inference import FEATURE_COLUMNS

    assert compose(None, {}, None, {})["guessed"] == []
    got = compose({"dw_probability": 0.01}, {"StreamsLast7Days_log": 1.0}, None, {})
    assert "StreamsLast7Days_log" not in got["guessed"]
    assert len(got["guessed"]) == len(FEATURE_COLUMNS) - 1


def _called(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    return {n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
            for n in ast.walk(tree) if isinstance(n, ast.Call)}


def test_the_free_page_draws_the_list_and_computes_no_contribution() -> None:
    from src.dashboard.views import algo_preview

    called = _called(algo_preview)
    assert "_render_guessed" in called and "imputed_features" in called
    assert not called & _SHAP_CALLS, f"the free preview computes a contribution: {called & _SHAP_CALLS}"


def test_the_rendered_list_carries_names_and_no_number() -> None:
    from streamlit.testing.v1 import AppTest

    def _app() -> None:
        from src.dashboard.views.algo_preview import _render_guessed
        _render_guessed(["StreamsLast7Days_log", "NonAlgoStreams28Days_log"])

    at = AppTest.from_function(_app).run()
    assert not at.exception
    from src.dashboard.utils.i18n import t
    from src.dashboard.views.trigger_algo._common._explain import _FEATURE_LABELS

    lines = [ln for m in at.markdown for ln in m.value.splitlines() if ln.startswith("- ")]
    # Exactly the labels, nothing appended — no weight, sign or percentage beside them.
    assert lines == [f"- {t(f'algo.label.{f}', _FEATURE_LABELS[f][0])}"
                     for f in ("StreamsLast7Days_log", "NonAlgoStreams28Days_log")], lines
