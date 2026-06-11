"""EN catalog for the shared ML decision-support widgets (ml_widgets.py)."""

EN = {
    # Classification scorecard
    "ml_widgets.no_scorecard": "No classification scorecard for this algorithm.",
    "ml_widgets.scorecard_title": "#### 📋 Classifier quality — {algo} "
                                  "(model `{model}`, {eval}, n={n})",
    "ml_widgets.auc_help": "95% interval: [{lo:.3f} – {hi:.3f}] "
                           "(N={n} → wide band, read with caution)",
    "ml_widgets.precision": "Precision",
    "ml_widgets.auc_ci_caption": "AUC validated per song (group-CV), 95% interval "
                                 "**[{lo:.3f} – {hi:.3f}]** — not a single point.",
    "ml_widgets.accuracy_trap": "⚠️ Accuracy trap: {acc:.1f}% vs "
                                "{base:.1f}% for a model that always predicts « failure ».",
    "ml_widgets.cm_pred_fail": "Predicted: Failure",
    "ml_widgets.cm_pred_trigger": "Predicted: Trigger",
    "ml_widgets.cm_real_fail": "Actual: Failure",
    "ml_widgets.cm_real_trigger": "Actual: Trigger",
    "ml_widgets.cm_tn": "TN {n}",
    "ml_widgets.cm_tp": "TP {n}",
    "ml_widgets.cm_title": "Confusion matrix (test set)",
    # Pre-release Release Radar estimator
    "ml_widgets.pre_rr_title": "#### 🔮 Release Radar simulator (pre-release)",
    "ml_widgets.pre_rr_caption": "Estimates Release Radar odds **before the first stream**, "
                                 "from release metadata alone (metadata-only model, AUC 0.92 "
                                 "validated per song). Planning tool — no data is stored.",
    "ml_widgets.pre_rr_followers": "Spotify followers",
    "ml_widgets.pre_rr_catalog": "Tracks already released",
    "ml_widgets.pre_rr_cadence": "Release cadence (weeks)",
    "ml_widgets.pre_rr_dm": "Discovery Mode enabled",
    "ml_widgets.pre_rr_dm_help": "Note: the model confirms that Discovery Mode does NOT "
                                 "influence Release Radar (flat effect) — useful for DW/Radio.",
    "ml_widgets.pre_rr_unavailable": "Pre-release model unavailable "
                                     "(artifact `rr_premiere_classifier` missing).",
    "ml_widgets.pre_rr_curve_title": "Release Radar probability by track age",
    "ml_widgets.pre_rr_xaxis": "days after release",
    "ml_widgets.pre_rr_peak": "🎯 Estimated eligibility peak at **D+{day}** "
                              "(**{prob:.0f}%**). Release Radar window 0–40 d.",
    "ml_widgets.pre_rr_band": "Metadata-only model: AUC {auc} [{lo}–{hi}] "
                              "(group-CV per song, N=508). Indicative estimate, not a guarantee.",
    "ml_widgets.calibration": "🎯 Calibration: {note}",
    # Local lever sensitivity
    "ml_widgets.sens_title": "**🎛️ Local sensitivity — move one lever on THIS track**",
    "ml_widgets.sens_select": "Lever to simulate",
    "ml_widgets.sens_unavailable": "Sensitivity unavailable (model or features missing).",
    "ml_widgets.sens_gain": " Moving from **{cur:,.0f}** to the target **{target:,.0f}** {unit}: "
                            "P({algo}) **{cur_p:.0f}% → {tp:.0f}%** ({delta:+.0f} pts).",
    "ml_widgets.sens_curve_title": "P({algo}) by « {label} »",
    "ml_widgets.sens_current": "White line = current value (~{cur:,.0f} {unit}).",
    "ml_widgets.sens_local_caveat": "⚠️ *Local* sensitivity to this track — not a general rule "
                                    "(the model is non-linear; the effect depends on the other "
                                    "variables).",
    # Feature decision gauges
    "ml_widgets.gauge_divergent": " — ⚠️ divergent signal (proxy, non-actionable)",
    "ml_widgets.gauge_volume_flat": " — ⬜ flat for volume (entry lever)",
    "ml_widgets.gauge_no_live": " — live value unavailable",
    "ml_widgets.no_feature_rules": "No feature rule available for this algorithm.",
    "ml_widgets.gauges_title": "#### 🎚️ Per-variable decision sliders",
    "ml_widgets.gauges_legend": "Zones: 🔴 malus · ⬜ neutral · 🟢 bonus · "
                                "white line = this track's value.",
    "ml_widgets.gauges_pedagogic": "Variables without a live value ({n}) — educational",
    # Volume forecast / regressor
    "ml_widgets.floor_forecast": "🛡️ {label}: **≥ ~{val:,} streams 7d** (guaranteed floor). "
                                 "{disclaimer}",
    "ml_widgets.floor_text": "≥ ~{val:,} (floor)",
    "ml_widgets.regressor_badge": "🍽️ Volume model: {note}",
    # Volume decision gauges
    "ml_widgets.no_volume_zones": "No volume zones yet for this algorithm.",
    "ml_widgets.volume_gauges_title": "#### 🔊 VOLUME sliders (how many streams, not the entry)",
    "ml_widgets.volume_gauges_caption": "Quality (saves, retention) buys the **entry ticket**; "
                                        "raw fuel (organic, recent spark) writes the **cheque**.",
    "ml_widgets.volume_gauges_pedagogic": "Volume variables without a live value ({n}) — "
                                          "educational",
    "ml_widgets.volume_imputed": "⚠️ {names}: no live value for this song — shown as "
                                 "**targets**, not live values. Manual-source variables "
                                 "(non-algo, Radio) display live as soon as they are entered "
                                 "in “🎯 Global View”.",
    # SHAP narrative
    "ml_widgets.shap_headline": "**🧾 {algo_label} autopsy** — average starting point: "
                                "~{baseline:,.0f} → prediction: **~{prediction:,.0f}**.",
    "ml_widgets.shap_neg": "❌ What pulls it down: {worst}.",
    "ml_widgets.shap_pos": "✅ What supports it: {best}.",
    # Prescriptive coach
    "ml_widgets.coach_title": "##### 🧭 Prescriptive coach",
    "ml_widgets.coach_ok": "✅ No critical action: the measurable levers are in the "
                           "neutral/bonus zone.",
    "ml_widgets.coach_smooth": "**{i}. Smooth the velocity** — currently {current:.2f}. {lever} "
                               "→ cut the ad budget (~−30%); concrete amount in the Budget & ROI "
                               "tab.",
    "ml_widgets.coach_raise": "**{i}. {label}** — {current:,.0f} {unit} "
                              "(target {target:,.0f}, short by {gap:,.0f}). {lever}",
    "ml_widgets.coach_radio_dm": "🎫 Check **Discovery Mode** (Spotify for Artists): strong Radio "
                                 "lever (pay-to-play, −30% royalties) — not measured automatically.",
}
