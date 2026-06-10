"""ML visuals for the PDF report — SHAP waterfalls + per-feature decision cursors.

Type: Sub
Uses: shap, xgboost (loaded lazily), algo_knowledge (pure data), ml_inference
Depends on: machine_learning/models/v3/*.ubj
Persists in: nothing

Isolated from pdf_exporter so the shap/xgboost weight stays contained. NEVER imports
streamlit. Every public function fails soft (returns [] / "") so a missing model or a
shap error degrades to "section omise", never a crash. Badges use the colored `.badge`
CSS spans (no emoji — WeasyPrint strips emoji from the final HTML).
"""
import base64
import io
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# (model_key, display label) — the 3 classifiers.
_ALGOS = [("dw_classifier", "Discover Weekly"),
          ("rr_classifier", "Release Radar"),
          ("radio_classifier", "Radio")]
_ZONE_BADGE = {"malus": ('red', 'malus'), "neutral": ('gray', 'neutre'),
               "bonus": ('green', 'bonus')}


def _feats(features_json):
    if isinstance(features_json, dict):
        return features_json
    try:
        return json.loads(features_json or "{}")
    except Exception:
        return {}


def _load_classifier(key):
    import xgboost as xgb
    from src.utils.ml_inference import MODEL_PATHS, _resolve_path
    m = xgb.Booster()
    m.load_model(_resolve_path(MODEL_PATHS[key]))
    return m


def _narrative(contribs):
    pos = sorted((c for c in contribs if c["value"] > 0), key=lambda c: -c["value"])[:3]
    neg = sorted((c for c in contribs if c["value"] < 0), key=lambda c: c["value"])[:3]
    parts = []
    if pos:
        parts.append("✅ <b>Soutient le score</b> : " + ", ".join(c["label"] for c in pos) + ".")
    if neg:
        parts.append("❌ <b>Pénalise</b> : " + ", ".join(c["label"] for c in neg) + ".")
    body = "<br>".join(parts) or "Contributions neutres."
    return (f"<p class='subtitle'>SHAP (log-odds, modèle non calibré) — barres rouges = "
            f"contribution positive, bleues = négative.<br>{body}</p>")


def shap_waterfalls(features_json):
    """[(algo_label, png_data_uri, narrative_html)] for DW/RR/Radio. [] on any failure."""
    feats = _feats(features_json)
    if not feats:
        return []
    try:
        import numpy as np
        import pandas as pd
        import shap
        from src.utils.ml_inference import FEATURE_COLUMNS
        from src.dashboard.views.trigger_algo._common import _FEATURE_LABELS
    except Exception:
        return []
    x_df = pd.DataFrame([[float(feats.get(f, 0.0)) for f in FEATURE_COLUMNS]],
                        columns=FEATURE_COLUMNS)
    out = []
    for key, label in _ALGOS:
        try:
            model = _load_classifier(key)
            sx = shap.TreeExplainer(model)(x_df)
            plt.figure(figsize=(8.2, 4.2))
            shap.plots.waterfall(sx[0], max_display=13, show=False)
            buf = io.BytesIO()
            plt.gcf().savefig(buf, format="png", dpi=120, bbox_inches="tight",
                              facecolor="white")
            plt.close("all")
            uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
            vals = [float(v) for v in np.ravel(sx[0].values)]
            contribs = [{"label": _FEATURE_LABELS.get(c, (c,))[0], "value": vals[i]}
                        for i, c in enumerate(FEATURE_COLUMNS) if i < len(vals)]
            out.append((label, uri, _narrative(contribs)))
        except Exception:
            continue
    return out


def decision_cursors_html(features_json):
    """Per-feature × algo (DW/RR/Radio) decision table: value + zone badge + top reco."""
    feats = _feats(features_json)
    if not feats:
        return ""
    try:
        from src.dashboard.utils import algo_knowledge as ak
    except Exception:
        return ""
    algos = ak.populated_algos()
    if not algos:
        return ""
    feat_ids = list(ak.ALGO_FEATURE_ZONES.get(algos[0], {}).keys())
    head = "".join(f"<th>{ak.ALGO_LABELS.get(a, a)}</th>" for a in algos)
    rows = []
    for fid in feat_ids:
        label, val = fid, None
        for a in algos:
            spec = ak.ALGO_FEATURE_ZONES.get(a, {}).get(fid)
            if spec:
                label = spec.get("label", fid)
                val = ak.decode_feature_value(a, fid, feats)
                break
        cells = ""
        for a in algos:
            z = ak.zone_for_value(a, fid, val) if val is not None else None
            if z in _ZONE_BADGE:
                cls, txt = _ZONE_BADGE[z]
                cells += f"<td><span class='badge {cls}'>{txt}</span></td>"
            else:
                cells += "<td>—</td>"
        vtxt = f"{val:,.0f}" if isinstance(val, (int, float)) else "—"
        rows.append(f"<tr><td>{label}</td><td>{vtxt}</td>{cells}</tr>")
    table = (f"<table class='compact'><thead><tr><th>Variable</th><th>Valeur</th>{head}"
             f"</tr></thead><tbody>{''.join(rows)}</tbody></table>")
    recos = []
    for a in algos:
        try:
            acts = ak.build_coach_actions(a, feats)
        except Exception:
            acts = []
        if acts:
            recos.append(f"<b>{ak.ALGO_LABELS.get(a, a)}</b> : {acts[0].get('lever', '')}")
    reco_html = ("<p class='subtitle'>Levier #1 par algo —<br>" + "<br>".join(recos) + "</p>"
                 if recos else "")
    return table + reco_html
