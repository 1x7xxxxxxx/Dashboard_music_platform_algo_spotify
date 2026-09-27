"""Streamlit/Plotly render helpers for ML decision-support widgets.

Type: Utility
Depends on: streamlit, plotly, algo_knowledge (pure config/helpers)
Persists in: nothing (renders into the current Streamlit context)

Shared between the end-user "Road to Algo" view (trigger_algo.py) and the admin
ML performance view (ml_performance.py). All domain numbers come from
algo_knowledge; this module is purely presentational.
"""
import streamlit as st
import plotly.graph_objects as go

from src.dashboard.utils import algo_knowledge as ak, charts
from src.dashboard.utils.platform_colors import ALGO_COLORS
from src.dashboard.utils.i18n import t

_VERDICT_BADGE = {"malus": "🔴", "neutral": "⬜", "bonus": "🟢"}


# ── i18n resolvers for algo_knowledge prose ───────────────────────────────────
# algo_knowledge.py is a pure, streamlit-free, unit-tested source of truth whose
# coaching prose stays French. These helpers translate at the RENDER layer: each
# maps a stable identifier already present in the data (registry kind + algo +
# feature, or algo alone) to a namespaced i18n key, with the FR data string as the
# `t()` default. EN translations live in i18n_catalog/trigger_algo.py. Keep the
# slug scheme stable so EN keys keep resolving.
def _registry_kind(registry: dict | None) -> str:
    """'vol' for the volume/regressor zones, 'entry' otherwise (classification).

    Callers pass the per-algo sub-dict (``ALGO_VOLUME_ZONES[algo]``), so identity
    against the top-level mapping is insufficient — match membership in its values.
    """
    if registry is ak.ALGO_VOLUME_ZONES or registry in ak.ALGO_VOLUME_ZONES.values():
        return "vol"
    return "entry"


def lever_text(algo: str, fid: str, spec: dict, registry: dict | None = None) -> str:
    """Translated lever advice for a (registry, algo, feature) zone spec."""
    kind = _registry_kind(registry)
    return t(f"algo.lever.{kind}.{algo}.{fid}", spec["lever"])


def label_text(fid: str, spec: dict) -> str:
    """Translated feature display label. Algo-independent: keyed by fid only."""
    return t(f"algo.label.{fid}", spec["label"])


def divergent_note_text(algo: str, fid: str, spec: dict) -> str:
    """Translated divergent-signal note (entry zones only carry these)."""
    return t(f"algo.divnote.{algo}.{fid}", spec["divergent_note"])


def regressor_note_text(algo: str) -> str | None:
    """Translated volume-regressor interpretation (hungry-model badge), or None."""
    note = ak.regressor_note(algo)
    if note is None:
        return None
    return t(f"algo.regressor.{algo}", note)


def model_interpretation_text(algo: str, fr_note: str) -> str:
    """Translated classification-scorecard interpretation for an algo."""
    return t(f"algo.model.{algo}", fr_note)


def suppressed_note_text(algo: str) -> str | None:
    """Translated 'forecast suppressed' caption for an unreliable regressor, or None."""
    note = ak.volume_suppressed_note(algo)
    if note is None:
        return None
    return t(f"algo.suppressed.{algo}", note)


def calibration_note_text(algo: str, raw) -> str | None:
    """Translated reliability band text for a raw classifier score, or None.

    Bands are keyed by their lower bound (×100, integer) so the slug stays stable
    even if a band's text is edited.
    """
    bands = ak.ALGO_CALIBRATION_BANDS.get(algo)
    if not bands or raw is None:
        return None
    for low, high, fr_text in bands:
        if low <= raw < high:
            return t(f"algo.calib.{algo}.{int(low * 100)}", fr_text)
    return None


def radio_recovery_text(feats: dict) -> str | None:
    """Translated Radio margin-recovery advice (cruising-velocity Discovery Mode), or None.

    The FR note is interpolated (current/target streams), so the i18n template keeps
    named {val}/{target} placeholders; we re-derive them here to .format() the EN side.
    """
    spec = ak._spec("RADIO", "StreamsLast7Days", registry=ak.ALGO_VOLUME_ZONES)
    if not spec:
        return None
    val = ak.decode_feature_value("RADIO", "StreamsLast7Days", feats,
                                  registry=ak.ALGO_VOLUME_ZONES)
    target = spec.get("target")
    if val is None or target is None or val < target:
        return None
    return t(
        "algo.recovery.radio",
        "💸 Vitesse de croisière atteinte (~{val:,.0f} streams/7j ≥ {target:,.0f}). "
        "Si Discovery Mode est activé sur ce titre, désactive-le : il a fait son travail "
        "d'entrée en Radio mais n'ajoute aucun volume (SHAP plat à zéro). Tu récupères "
        "~30% de royalties — l'algo continue de pousser via ta vélocité organique."
    ).format(val=val, target=target)


# ── Classification scorecard (used by both views) ─────────────────────────────
def render_classification_scorecard(algo: str, *, compact: bool = False) -> None:
    m = ak.ALGO_MODEL_METRICS.get(algo)
    if not m:
        st.info(t("ml_widgets.no_scorecard",
                  "Pas de scorecard de classification pour cet algorithme."))
        return
    _eval = m.get("eval", "test")
    st.markdown(t("ml_widgets.scorecard_title",
                  "#### 📋 Qualité du classifieur — {algo} "
                  "(modèle `{model}`, {eval}, n={n})"
                  ).format(algo=algo, model=m['model_version'], eval=_eval, n=m['test_n']))
    cols = st.columns(5)
    _ci = m.get("auc_ci")
    cols[0].metric("AUC", f"{m['auc']:.3f}",
                   help=(t("ml_widgets.auc_help",
                           "Intervalle 95% : [{lo:.3f} – {hi:.3f}] "
                           "(N={n} → bande large, à lire avec prudence)"
                           ).format(lo=_ci[0], hi=_ci[1], n=m['test_n'])
                         if _ci else None))
    cols[1].metric(t("ml_widgets.precision", "Précision"), f"{m['precision'] * 100:.0f}%")
    cols[2].metric("Recall", f"{m['recall'] * 100:.0f}%")
    cols[3].metric("F1", f"{m['f1']:.2f}")
    cols[4].metric("Lift top-10%", f"×{m['lift_top10']:.1f}")
    if _ci:
        st.caption(t("ml_widgets.auc_ci_caption",
                     "AUC validée par chanson (group-CV), intervalle 95% "
                     "**[{lo:.3f} – {hi:.3f}]** — pas un point unique."
                     ).format(lo=_ci[0], hi=_ci[1]))
    st.caption(t("ml_widgets.accuracy_trap",
                 "⚠️ Piège accuracy : {acc:.1f}% vs "
                 "{base:.1f}% pour un modèle qui prédirait toujours « échec »."
                 ).format(acc=m['accuracy'] * 100, base=m['baseline_accuracy'] * 100))
    if compact:
        return
    cm = m["confusion"]
    fig = go.Figure(data=go.Heatmap(
        z=[[cm["TN"], cm["FP"]], [cm["FN"], cm["TP"]]],
        x=[t("ml_widgets.cm_pred_fail", "Prédit : Échec"),
           t("ml_widgets.cm_pred_trigger", "Prédit : Trigger")],
        y=[t("ml_widgets.cm_real_fail", "Réel : Échec"),
           t("ml_widgets.cm_real_trigger", "Réel : Trigger")],
        text=[[t("ml_widgets.cm_tn", "VN {n}").format(n=cm['TN']), f"FP {cm['FP']}"],
              [f"FN {cm['FN']}", t("ml_widgets.cm_tp", "VP {n}").format(n=cm['TP'])]],
        texttemplate="%{text}", textfont={"size": 18},
        colorscale="Greens", showscale=False,
    ))
    fig.update_layout(height=320, title=t("ml_widgets.cm_title",
                                          "Matrice de confusion (jeu de test)"),
                      margin=dict(t=50))
    charts.plotly_chart(fig, width="stretch", key=f"cm_{algo}")
    st.info(model_interpretation_text(algo, m["interpretation"]))


# ── Pre-release Release Radar estimator (what-if, no DB) ──────────────────────
def render_lever_sensitivity(algo: str, feats: dict) -> None:
    """For THIS song, sweep one actionable lever and plot the calibrated-prob curve.

    Honest *local* partial dependence — specific to this song's other features, NOT a
    global "+X saves = +Y%" rule (the model is non-linear). Lets the artist see the real
    marginal payoff of pushing a lever toward its target. Picks the actionable, live
    levers from ALGO_FEATURE_ZONES; degrades silently if the model/features are absent.
    """
    import numpy as np

    from src.utils.ml_inference import local_sensitivity

    zones = ak.ALGO_FEATURE_ZONES.get(algo, {})
    levers = {label_text(fid, spec): (fid, spec) for fid, spec in zones.items()
              if spec.get("json_key") and ak.feature_live_available(spec, feats)
              and spec.get("actionable") is not False}
    if not levers or not feats:
        return
    st.markdown(t("ml_widgets.sens_title",
                  "**🎛️ Sensibilité locale — bouger un levier sur CE titre**"))
    # R247 (fiche 57, owner : « je ne comprends pas l'intérêt : modifie et explique »).
    st.caption(t("ml_widgets.sens_plain",
                 "La question : si tu poussais **ce seul levier**, tout le reste du titre "
                 "inchangé, la chance que le modèle donne à {algo} monterait-elle ? Une "
                 "courbe plate veut dire non — ce levier seul ne suffit pas.").format(algo=algo))
    choice = st.selectbox(t("ml_widgets.sens_select", "Levier à simuler"),
                          list(levers), key=f"sens_sel_{algo}")
    fid, spec = levers[choice]
    target = spec.get("target")
    res = local_sensitivity(algo, spec["json_key"], feats,
                            targets=(target,) if target else ())
    if res is None:
        st.caption(t("ml_widgets.sens_unavailable",
                     "Sensibilité indisponible (modèle ou features absents)."))
        return
    xs = res["x_human"]
    probs = [p * 100 for p in res["probs"]]
    cur = res["current"]
    # `cur` and `target` are exact grid points (local_sensitivity inserts them), so
    # these reads are model values, not interpolations across a coarse segment.
    cur_p = float(np.interp(cur, xs, probs))
    unit = spec.get("unit", "")
    # A `_log` lever spans 0..~221k streams: on a linear axis 0..10k (where the model
    # responds) would take 4 % of the width. Plot against log1p with human ticks.
    to_ax = (lambda v: float(np.log1p(max(v, 0.0)))) if res.get("log_scale") else float
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[to_ax(x) for x in xs], y=probs, customdata=xs, mode="lines",
                             line=dict(color=ALGO_COLORS.get(algo, ALGO_COLORS["DW"]), width=3),
                             hovertemplate="%{customdata:,.0f} → %{y:.1f} %<extra></extra>"))
    fig.add_vline(x=to_ax(cur), line_color="#666666", line_dash="dash", line_width=2)
    if res.get("log_scale"):
        ticks = [v for v in (0, 10, 100, 1_000, 10_000, 100_000, 1_000_000) if v <= xs[-1]]
        fig.update_xaxes(tickvals=[to_ax(v) for v in ticks],
                         ticktext=[f"{v:,.0f}".replace(",", " ") for v in ticks])
    gain_msg = ""
    if target:
        tp = float(np.interp(target, xs, probs))
        fig.add_vline(x=to_ax(target), line_color="orange", line_dash="dot", line_width=2)
        gain_msg = t("ml_widgets.sens_gain",
                     " Passer de **{cur:,.0f}** à la cible **{target:,.0f}** {unit} : "
                     "P({algo}) **{cur_p:.0f}% → {tp:.0f}%** ({delta:+.0f} pts)."
                     ).format(cur=cur, target=target, unit=unit, algo=algo,
                              cur_p=cur_p, tp=tp, delta=tp - cur_p)
    fig.update_layout(height=240, margin=dict(t=30, b=30), showlegend=False,
                      title=t("ml_widgets.sens_curve_title",
                              "P({algo}) selon « {label} »"
                              ).format(algo=algo, label=label_text(fid, spec)),
                      xaxis_title=unit or label_text(fid, spec), yaxis_title="P %",
                      yaxis_range=[0, 100])
    charts.plotly_chart(fig, width="stretch", key=f"sens_curve_{algo}_{fid}")
    st.caption(t("ml_widgets.sens_current",
                 "Tirets gris = valeur actuelle (~{cur:,.0f} {unit})."
                 ).format(cur=cur, unit=unit) + gain_msg)
    st.markdown(sensitivity_verdict(probs, label_text(fid, spec)))
    st.caption(t("ml_widgets.sens_local_caveat",
                 "⚠️ Sensibilité *locale* à ce titre — pas une règle générale "
                 "(le modèle est non-linéaire ; l'effet dépend des autres variables)."))


# Below this span (in points of probability) across the whole sweep, the curve is FLAT:
# the model's opinion does not move with this lever. 2 points = about the width of the
# line on a 0-100 axis; the note of 2026-09-27 measured P(DW) at ~15 % from 0 to 200 k.
_FLAT_SPAN_PTS = 2.0


def sensitivity_verdict(probs_pct, label: str) -> str:
    """The decision a sensitivity curve supports, in words. Pure."""
    span = max(probs_pct) - min(probs_pct) if probs_pct else 0.0
    if span < _FLAT_SPAN_PTS:
        return t("ml_widgets.sens_flat",
                 "➖ **Courbe plate** : pousser « {label} » seul ne change pas l'avis du "
                 "modèle sur ce titre. Ne mise pas tout sur ce levier.").format(label=label)
    return t("ml_widgets.sens_moves",
             "📈 **Ce levier compte** : sur toute la plage, la chance bouge de {span:.0f} "
             "points. C'est un levier à pousser.").format(span=span)


# ── Calibration badge ─────────────────────────────────────────────────────────
def render_calibration_badge(algo: str, raw) -> None:
    note = calibration_note_text(algo, raw)
    if note:
        st.caption(t("ml_widgets.calibration", "🎯 Calibration : {note}").format(note=note))


# ── Feature decision tables ───────────────────────────────────────────────────
# ONE table per (algo, registry), never one figure per feature. Until 2026-09-26 each
# registry entry drew its own zone-bar figure: 38 figures on one tab of ml_performance
# (13+6+9 entry + 4+6 volume), a count that grew with the knowledge registry and that
# no first-screen ceiling could see, because it counts call sites, not calls. The rows
# carry the same facts — value, gates, gap, verdict, lever — and add none.
# Guard: tests/test_a_helper_does_not_draw_one_figure_per_registry_entry.py.
def _num(x) -> str:
    """Compact human number: thousands separated, small ratios keep their decimals."""
    if abs(x) >= 100 or float(x).is_integer():
        return f"{x:,.0f}"
    return f"{x:.2g}"


def _gates_text(spec: dict) -> str:
    """The zone bounds of a spec, badge by badge — read from spec['zones'], nothing new."""
    parts = []
    for low, high, verdict, _note in spec["zones"]:
        badge = _VERDICT_BADGE.get(verdict, "▫️")
        if high is None:
            parts.append(f"{badge} ≥ {_num(low or 0)}")
        else:
            parts.append(f"{badge} {_num(low or 0)}–{_num(high)}")
    return " · ".join(parts)


def _gap_to_bonus(spec: dict, live) -> float | None:
    """Signed distance from `live` to the nearest bonus zone bound (0 inside one).

    None when there is no live value or the spec has no bonus zone. Positive = to add,
    negative = to remove. Reads the same bounds `ak.zone_for_value` reads.
    """
    if live is None:
        return None
    gaps = []
    for low, high, verdict, _note in spec["zones"]:
        if verdict != "bonus":
            continue
        lo = low if low is not None else float("-inf")
        hi = high if high is not None else float("inf")
        gaps.append(0.0 if lo <= live < hi else (lo - live if live < lo else hi - live))
    return min(gaps, key=abs) if gaps else None


def _note_text(algo: str, fid: str, spec: dict) -> str:
    notes = []
    if spec.get("divergent"):
        notes.append(t("ml_widgets.note_divergent",
                       "⚠️ signal divergent (proxy, non-actionnable)"))
    if spec.get("volume_flat"):
        notes.append(t("ml_widgets.note_volume_flat", "⬜ plat pour le volume (levier d'entrée)"))
    if spec.get("divergent_note"):
        notes.append(divergent_note_text(algo, fid, spec))
    return " ".join(notes)


def _gauge_row(algo: str, fid: str, spec: dict, live, registry: dict | None) -> dict:
    unit = spec.get("unit", "")
    verdict = ak.zone_for_value(algo, fid, live, registry=registry)
    gap = _gap_to_bonus(spec, live)
    if gap is None:
        gap_txt = "—"
    elif gap == 0:
        gap_txt = t("ml_widgets.gap_reached", "✓ en zone bonus")
    else:
        gap_txt = f"{'+' if gap > 0 else '−'}{_num(abs(gap))} {unit}"
    return {
        t("ml_widgets.col_indicator", "Indicateur"): label_text(fid, spec),
        t("ml_widgets.col_value", "Valeur"): "—" if live is None else f"{_num(live)} {unit}",
        t("ml_widgets.col_gates", "Portes"): _gates_text(spec),
        t("ml_widgets.col_gap", "Écart au bonus"): gap_txt,
        t("ml_widgets.col_verdict", "Verdict"): _VERDICT_BADGE.get(verdict, "▫️"),
        t("ml_widgets.col_lever", "Levier"): lever_text(algo, fid, spec, registry=registry),
        t("ml_widgets.col_note", "Note"): _note_text(algo, fid, spec),
    }


def _render_gauge_table(algo: str, rows: list, registry: dict | None) -> None:
    """ONE st.dataframe for every (fid, spec, live) of a registry — live rows first."""
    import pandas as pd

    ordered = sorted(rows, key=lambda r: r[2] is None)  # stable: registry order kept
    st.dataframe(pd.DataFrame([_gauge_row(algo, fid, spec, live, registry)
                               for fid, spec, live in ordered]),
                 hide_index=True, width="stretch")


def _live_value(algo: str, fid: str, spec: dict, feats: dict, registry: dict | None = None):
    """Live value only when honestly available (manual-source features count as live
    once the tenant has entered them — see ak.feature_live_available)."""
    if not ak.feature_live_available(spec, feats):
        return None
    return ak.decode_feature_value(algo, fid, feats, registry=registry)


def render_feature_gauges(algo: str, feats: dict) -> None:
    feats = feats or {}
    ids = ak.feature_ids(algo)
    if not ids:
        st.info(t("ml_widgets.no_feature_rules",
                  "Aucune règle de feature disponible pour cet algorithme."))
        return
    zones = ak.ALGO_FEATURE_ZONES[algo]
    st.markdown(t("ml_widgets.gauges_title", "#### 🎚️ Curseurs de décision par variable"))
    st.caption(t("ml_widgets.gauges_table_legend",
                 "Une ligne par variable. Verdict : 🔴 malus · ⬜ neutre · 🟢 bonus. "
                 "Écart = ce qu'il manque (+) ou ce qui dépasse (−) pour atteindre la "
                 "zone bonus la plus proche."))
    rows = [(fid, zones[fid], _live_value(algo, fid, zones[fid], feats)) for fid in ids]
    _render_gauge_table(algo, rows, None)
    n_ped = sum(1 for _fid, _spec, live in rows if live is None)
    if n_ped:
        st.caption(t("ml_widgets.gauges_pedagogic",
                     "Variables sans valeur live ({n}) — pédagogique").format(n=n_ped)
                   + " : « — ».")


# ── Volume forecast: floor reframing + hungry-model badge ─────────────────────
def render_floor_forecast(label: str, forecast, *, algo: str = "DW") -> None:
    """Render a *_streams_forecast_7d value as a conservative FLOOR, not a point
    estimate. Single-sourced wording (algo_knowledge) so every surface agrees."""
    if forecast is None:
        return
    try:
        val = int(forecast)
    except (TypeError, ValueError):
        return
    st.caption(t("ml_widgets.floor_forecast",
                 "🛡️ {label} : **≥ ~{val:,} streams 7j** (plancher garanti). {disclaimer}"
                 ).format(label=label, val=val,
                          disclaimer=t("algo.disclaimer.floor", ak.FORECAST_FLOOR_DISCLAIMER)))


def floor_forecast_text(forecast) -> str | None:
    """Plain-text floor phrasing for tables/tooltips. None if no forecast."""
    if forecast is None:
        return None
    try:
        return t("ml_widgets.floor_text", "≥ ~{val:,} (plancher)").format(val=int(forecast))
    except (TypeError, ValueError):
        return None


def render_regressor_badge(algo: str) -> None:
    """'Hungry / conservative model' badge for the volume regressor."""
    note = regressor_note_text(algo)
    if note:
        st.caption(t("ml_widgets.regressor_badge",
                     "🍽️ Modèle de volume : {note}").format(note=note))


# ── Volume decision gauges (regressor zones) ──────────────────────────────────
def render_volume_gauges(algo: str, feats: dict) -> None:
    """Render the VOLUME (regressor) decision zones — distinct from the entry zones.

    Surfaces the 'quality buys the ticket, volume writes the cheque' insight:
    raw-fuel levers (recent streams, organic traffic) drive volume; saves/playlist
    adds are flagged flat-for-volume. Imputed features (NonAlgoStreams) sit in the
    same table with value « — », exactly like the entry table.
    """
    feats = feats or {}
    ids = ak.volume_feature_ids(algo)
    if not ids:
        st.info(t("ml_widgets.no_volume_zones",
                  "Pas encore de zones de volume pour cet algorithme."))
        return
    zones = ak.ALGO_VOLUME_ZONES[algo]
    st.markdown(t("ml_widgets.volume_gauges_title",
                  "#### 🔊 Curseurs de VOLUME (combien de streams, pas l'entrée)"))
    st.caption(t("ml_widgets.volume_gauges_caption",
                 "La qualité (saves, rétention) achète le **ticket d'entrée** ; le "
                 "carburant brut (organique, étincelle récente) écrit le **chèque**."))
    render_regressor_badge(algo)
    rows = [(fid, zones[fid], _live_value(algo, fid, zones[fid], feats, registry=zones))
            for fid in ids]
    _render_gauge_table(algo, rows, zones)
    pedagogic = [(fid, spec) for fid, spec, live in rows if live is None]
    if pedagogic:
        _imputed = ", ".join(label_text(_fid, spec) for _fid, spec in pedagogic)
        st.caption(t("ml_widgets.volume_gauges_pedagogic",
                     "Variables volume sans valeur live ({n}) — pédagogique"
                     ).format(n=len(pedagogic)) + " — " +
                   t("ml_widgets.volume_imputed",
                     "⚠️ {names} : pas de valeur live pour ce titre — affichées comme "
                     "**cibles**, pas valeurs live. Les variables à source manuelle "
                     "(non-algo, Radio) s'affichent en live dès qu'elles sont saisies "
                     "dans « 🎯 Vue Globale »."
                     ).format(names=_imputed))


# ── SHAP waterfall narrative (natural-language autopsy) ───────────────────────
def render_shap_narrative(algo_label: str, baseline: float, prediction: float,
                          contributions: list[dict]) -> None:
    """Turn a SHAP waterfall into a plain-language 'receipt'.

    contributions: list of {"label": str, "value": float} in streams space (already
    decoded from log-odds / model output), sorted by importance is not required.
    """
    if not contributions:
        return
    pos = sorted([c for c in contributions if c["value"] > 0],
                 key=lambda c: c["value"], reverse=True)[:3]
    neg = sorted([c for c in contributions if c["value"] < 0],
                 key=lambda c: c["value"])[:3]
    lines = [t("ml_widgets.shap_headline",
               "**🧾 Autopsie {algo_label}** — point de départ moyen : "
               "~{baseline:,.0f} → prédiction : **~{prediction:,.0f}**."
               ).format(algo_label=algo_label, baseline=baseline, prediction=prediction)]
    if neg:
        worst = ", ".join(f"{c['label']} ({c['value']:,.0f})" for c in neg)
        lines.append(t("ml_widgets.shap_neg",
                       "❌ Ce qui tire vers le bas : {worst}.").format(worst=worst))
    if pos:
        best = ", ".join(f"{c['label']} (+{c['value']:,.0f})" for c in pos)
        lines.append(t("ml_widgets.shap_pos",
                       "✅ Ce qui soutient : {best}.").format(best=best))
    st.markdown("  \n".join(lines))


# ── Prescriptive coach (ranked to-do list) ────────────────────────────────────
def render_coach(algo: str, feats: dict) -> None:
    """Ranked prescriptive actions for an algo. Velocity-too-high → smooth advice
    (concrete spend cut shown in the Budget tab); others → raise-to-target."""
    feats = feats or {}
    if not ak.feature_ids(algo):
        return
    st.markdown(t("ml_widgets.coach_title", "##### 🧭 Coach prescriptif"))
    actions = ak.build_coach_actions(algo, feats)
    if not actions:
        st.success(t("ml_widgets.coach_ok",
                     "✅ Aucune action critique : les leviers mesurables sont en zone "
                     "neutre/bonus."))
    for i, a in enumerate(actions, 1):
        _lever = lever_text(algo, a["feature"], a)
        _label = label_text(a["feature"], a)
        if a["kind"] == "smooth":
            st.error(t("ml_widgets.coach_smooth",
                       "**{i}. Lisser la vélocité** — actuelle {current:.2f}. {lever} "
                       "→ réduis le budget pub (~−30%) ; montant concret dans l'onglet "
                       "Budget & ROI."
                       ).format(i=i, current=a['current'], lever=_lever))
        else:
            st.warning(t("ml_widgets.coach_raise",
                         "**{i}. {label}** — {current:,.0f} {unit} "
                         "(objectif {target:,.0f}, manque {gap:,.0f}). {lever}"
                         ).format(i=i, label=_label, current=a['current'],
                                  unit=a['unit'], target=a['target'],
                                  gap=a['gap'], lever=_lever))
    if algo == "RADIO":
        st.info(t("ml_widgets.coach_radio_dm",
                  "🎫 Vérifie **Discovery Mode** (Spotify for Artists) : fort levier Radio "
                  "(pay-to-play, −30% royalties) — non mesuré automatiquement."))
