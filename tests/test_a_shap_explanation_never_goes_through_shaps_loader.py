"""R242 — SHAP explanations are computed by XGBoost, never by `shap.TreeExplainer`.

XGBoost 3 writes `base_score` as a list; shap 0.49 cannot parse it and raised on every
waterfall of the app and of the artist PDF, in production, behind a friendly warning
(found 2026-09-27 by rendering the explainability tab for the charts dossier).
"""
import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def tree_explainer_calls(tree: ast.AST) -> list[int]:
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", getattr(n.func, "id", "")) == "TreeExplainer"]


def test_no_surface_calls_shaps_tree_loader():
    hits = [f"{f.relative_to(ROOT)}:{ln}" for f in (ROOT / "src").rglob("*.py")
            for ln in tree_explainer_calls(ast.parse(f.read_text(encoding="utf-8")))]
    assert not hits, f"use src.utils.shap_explain.explain() instead: {hits}"


def test_the_detector_sees_the_defect_it_is_written_for():
    assert tree_explainer_calls(ast.parse("e = shap.TreeExplainer(m)(x)"))
    assert not tree_explainer_calls(ast.parse("# shap.TreeExplainer(m)\ne = explain(m, x)"))


@pytest.mark.parametrize("name", ["dw_classifier", "dw_regressor"])
def test_the_explanation_adds_up_to_the_model_margin(name):
    pytest.importorskip("shap")
    xgb = pytest.importorskip("xgboost")
    from src.utils.ml_inference import FEATURE_COLUMNS, load_model
    from src.utils.shap_explain import explain
    model = load_model(name)
    X = pd.DataFrame([np.linspace(0, 1, len(FEATURE_COLUMNS))], columns=FEATURE_COLUMNS)
    ex = explain(model, X)
    booster = model.get_booster() if hasattr(model, "get_booster") else model
    margin = float(booster.predict(xgb.DMatrix(X), output_margin=True)[0])
    assert abs(float(ex.values[0].sum() + ex.base_values[0]) - margin) < 1e-4
    assert list(ex.feature_names) == list(FEATURE_COLUMNS)
