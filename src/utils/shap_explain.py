"""SHAP values of an XGBoost model, computed by XGBoost itself — never by shap's loader.

Type: Utility
Uses: xgboost (TreeSHAP via `pred_contribs`), shap (the `Explanation` container and plots)
Triggers: views/trigger_algo/_tab_explainability.py, dashboard/utils/pdf_ml.py
Persists in: nothing

R242 (2026-09-27). `shap.TreeExplainer` parses the model's raw dump, and XGBoost 3 writes
`base_score` as a LIST (« [2.0472442E-1] »): shap 0.49 raises `could not convert string to
float`. Every SHAP waterfall of the app and of the artist PDF was replaced by a warning, in
production, and nothing reported it — the dossier found it by trying to render the tab.

XGBoost computes the exact same TreeSHAP contributions natively (`pred_contribs=True`, last
column = the bias), so the explanation no longer depends on two libraries agreeing on a
file format. Checked on dw_classifier and dw_regressor: Σ values + base = the model margin.
"""
from __future__ import annotations

import pandas as pd


def explain(model, X: pd.DataFrame):
    """A `shap.Explanation` for each row of X — values, base value, data, feature names."""
    import shap
    import xgboost as xgb
    booster = model.get_booster() if hasattr(model, "get_booster") else model
    contribs = booster.predict(xgb.DMatrix(X), pred_contribs=True)
    return shap.Explanation(values=contribs[:, :-1], base_values=contribs[:, -1],
                            data=X.values, feature_names=list(X.columns))
