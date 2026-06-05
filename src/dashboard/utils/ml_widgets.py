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

from src.dashboard.utils import algo_knowledge as ak

_VERDICT_FILL = {
    "malus": "rgba(255,107,107,0.35)",
    "neutral": "rgba(150,150,150,0.30)",
    "bonus": "rgba(29,185,84,0.35)",
}
_VERDICT_BADGE = {"malus": "🔴", "neutral": "⬜", "bonus": "🟢"}


# ── Classification scorecard (used by both views) ─────────────────────────────
def render_classification_scorecard(algo: str, *, compact: bool = False) -> None:
    m = ak.ALGO_MODEL_METRICS.get(algo)
    if not m:
        st.info("Pas de scorecard de classification pour cet algorithme.")
        return
    _eval = m.get("eval", "test")
    st.markdown(f"#### 📋 Qualité du classifieur — {algo} "
                f"(modèle `{m['model_version']}`, {_eval}, n={m['test_n']})")
    cols = st.columns(5)
    _ci = m.get("auc_ci")
    cols[0].metric("AUC", f"{m['auc']:.3f}",
                   help=(f"Intervalle 95% : [{_ci[0]:.3f} – {_ci[1]:.3f}] "
                         f"(N={m['test_n']} → bande large, à lire avec prudence)"
                         if _ci else None))
    cols[1].metric("Précision", f"{m['precision'] * 100:.0f}%")
    cols[2].metric("Recall", f"{m['recall'] * 100:.0f}%")
    cols[3].metric("F1", f"{m['f1']:.2f}")
    cols[4].metric("Lift top-10%", f"×{m['lift_top10']:.1f}")
    if _ci:
        st.caption(f"AUC validée par chanson (group-CV), intervalle 95% "
                   f"**[{_ci[0]:.3f} – {_ci[1]:.3f}]** — pas un point unique.")
    st.caption(
        f"⚠️ Piège accuracy : {m['accuracy'] * 100:.1f}% vs "
        f"{m['baseline_accuracy'] * 100:.1f}% pour un modèle qui prédirait toujours « échec »."
    )
    if compact:
        return
    cm = m["confusion"]
    fig = go.Figure(data=go.Heatmap(
        z=[[cm["TN"], cm["FP"]], [cm["FN"], cm["TP"]]],
        x=["Prédit : Échec", "Prédit : Trigger"],
        y=["Réel : Échec", "Réel : Trigger"],
        text=[[f"VN {cm['TN']}", f"FP {cm['FP']}"], [f"FN {cm['FN']}", f"VP {cm['TP']}"]],
        texttemplate="%{text}", textfont={"size": 18},
        colorscale="Greens", showscale=False,
    ))
    fig.update_layout(height=320, title="Matrice de confusion (jeu de test)",
                      margin=dict(t=50))
    st.plotly_chart(fig, width="stretch", key=f"cm_{algo}")
    st.info(m["interpretation"])


# ── Pre-release Release Radar estimator (what-if, no DB) ──────────────────────
def render_prerelease_rr_estimator() -> None:
    """Ephemeral RR-odds calculator from release-day metadata only (no streams).

    Exploits the v3 finding (forecast.md §5): RR keeps AUC ~0.92 from artist size +
    catalogue + release timing ALONE, so its odds are estimable BEFORE the first stream.
    Pure what-if — no DB write. Renders inputs + the RR-probability curve over the firing
    window (0–40 days). Degrades to an info box if the metadata-only model is unavailable.
    """
    from src.utils.ml_inference import estimate_rr_prerelease

    st.markdown("#### 🔮 Simulateur Release Radar (pré-sortie)")
    st.caption("Estime les chances Release Radar **avant la moindre écoute**, à partir des "
               "seules métadonnées de sortie (modèle métadonnées-seules, AUC 0.92 validée "
               "par chanson). Outil de planification — aucune donnée enregistrée.")
    c1, c2, c3 = st.columns(3)
    followers = c1.number_input("Followers Spotify", min_value=0, value=3000, step=100,
                                key="pre_rr_followers")
    catalog = c2.number_input("Titres déjà sortis", min_value=0, value=12, step=1,
                              key="pre_rr_catalog")
    cadence = c3.number_input("Cadence de sortie (semaines)", min_value=0.0, value=4.0,
                              step=0.5, key="pre_rr_cadence")
    discovery = st.checkbox("Discovery Mode activé", value=False, key="pre_rr_dm",
                            help="Note : le modèle confirme que Discovery Mode n'influence "
                                 "PAS Release Radar (effet plat) — utile pour DW/Radio.")

    probe = estimate_rr_prerelease(followers, 14, catalog, cadence, discovery)
    if probe is None:
        st.info("Modèle pré-sortie indisponible (artefact `rr_premiere_classifier` absent).")
        return

    days = list(range(0, 41))
    probs = [estimate_rr_prerelease(followers, d, catalog, cadence, discovery)["rr_probability"]
             for d in days]
    best_i = max(range(len(days)), key=lambda i: probs[i])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=days, y=[p * 100 for p in probs], mode="lines",
                             line=dict(color="rgb(255,165,0)", width=3), name="P(RR)"))
    fig.add_vline(x=days[best_i], line_color="#ffffff", line_dash="dash", line_width=2)
    fig.update_layout(height=260, margin=dict(t=30, b=30),
                      title="Probabilité Release Radar selon l'âge du titre",
                      xaxis_title="jours après sortie", yaxis_title="P(RR) %",
                      yaxis_range=[0, 100], showlegend=False)
    st.plotly_chart(fig, width="stretch", key="pre_rr_curve")
    cv = probe.get("cv", {})
    band = cv.get("auc_ci")
    st.success(f"🎯 Pic d'éligibilité estimé à **J+{days[best_i]}** "
               f"(**{probs[best_i] * 100:.0f}%**). Fenêtre Release Radar 0–40 j.")
    if band:
        st.caption(f"Modèle métadonnées-seules : AUC {cv.get('auc')} [{band[0]}–{band[1]}] "
                   "(group-CV par chanson, N=508). Estimation indicative, pas une garantie.")
    note = ak.calibration_note("RR", probs[best_i])
    if note:
        st.caption(f"🎯 Calibration : {note}")


# ── Local lever sensitivity (per-song partial dependence) ─────────────────────
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
    levers = {spec["label"]: (fid, spec) for fid, spec in zones.items()
              if spec.get("json_key") and not spec.get("live_unavailable")
              and not spec.get("divergent") and spec.get("actionable") is not False}
    if not levers or not feats:
        return
    st.markdown("**🎛️ Sensibilité locale — bouger un levier sur CE titre**")
    choice = st.selectbox("Levier à simuler", list(levers), key=f"sens_sel_{algo}")
    fid, spec = levers[choice]
    res = local_sensitivity(algo, spec["json_key"], feats)
    if res is None:
        st.caption("Sensibilité indisponible (modèle ou features absents).")
        return
    xs = res["x_human"]
    probs = [p * 100 for p in res["probs"]]
    cur = res["current"]
    cur_p = float(np.interp(cur, xs, probs))
    unit = spec.get("unit", "")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=probs, mode="lines", line=dict(color="#1DB954", width=3)))
    fig.add_vline(x=cur, line_color="#ffffff", line_dash="dash", line_width=2)
    target = spec.get("target")
    gain_msg = ""
    if target:
        tp = float(np.interp(target, xs, probs))
        fig.add_vline(x=target, line_color="orange", line_dash="dot", line_width=2)
        gain_msg = (f" Passer de **{cur:,.0f}** à la cible **{target:,.0f}** {unit} : "
                    f"P({algo}) **{cur_p:.0f}% → {tp:.0f}%** ({tp - cur_p:+.0f} pts).")
    fig.update_layout(height=240, margin=dict(t=30, b=30), showlegend=False,
                      title=f"P({algo}) selon « {spec['label']} »",
                      xaxis_title=unit or spec["label"], yaxis_title="P %",
                      yaxis_range=[0, 100])
    st.plotly_chart(fig, width="stretch", key=f"sens_curve_{algo}_{fid}")
    st.caption(f"Trait blanc = valeur actuelle (~{cur:,.0f} {unit})." + gain_msg)
    st.caption("⚠️ Sensibilité *locale* à ce titre — pas une règle générale "
               "(le modèle est non-linéaire ; l'effet dépend des autres variables).")


# ── Calibration badge ─────────────────────────────────────────────────────────
def render_calibration_badge(algo: str, raw) -> None:
    note = ak.calibration_note(algo, raw)
    if note:
        st.caption(f"🎯 Calibration : {note}")


# ── Feature decision gauges ───────────────────────────────────────────────────
def _axis_max(spec: dict, live):
    highs = [h for _lo, h, _v, _n in spec["zones"] if h is not None]
    amax = max(highs) * 1.25 if highs else 1.0
    if live is not None:
        amax = max(amax, live * 1.1)
    if spec.get("target"):
        amax = max(amax, spec["target"] * 1.2)
    return amax or 1.0


def _zone_bar_fig(spec: dict, live):
    amax = _axis_max(spec, live)
    fig = go.Figure()
    for low, high, verdict, _note in spec["zones"]:
        fig.add_shape(type="rect", layer="below", line_width=0,
                      x0=(low or 0), x1=(high if high is not None else amax),
                      y0=0, y1=1, fillcolor=_VERDICT_FILL[verdict])
    if live is not None:
        fig.add_vline(x=min(live, amax), line_color="#ffffff", line_width=3)
    fig.update_xaxes(range=[0, amax], showgrid=False, zeroline=False)
    fig.update_yaxes(range=[0, 1], showticklabels=False, showgrid=False, zeroline=False)
    fig.update_layout(height=80, margin=dict(l=0, r=0, t=8, b=22), showlegend=False)
    return fig


def _render_one_gauge(algo: str, fid: str, spec: dict, live, *,
                      registry: dict | None = None, key_prefix: str = "gauge") -> None:
    head = f"**{spec['label']}**"
    if live is not None:
        verdict = ak.zone_for_value(algo, fid, live, registry=registry)
        head += f" — {live:,.0f} {spec['unit']} {_VERDICT_BADGE.get(verdict, '▫️')}"
    elif spec.get("divergent"):
        head += " — ⚠️ signal divergent (proxy, non-actionnable)"
    elif spec.get("volume_flat"):
        head += " — ⬜ plat pour le volume (levier d'entrée)"
    else:
        head += " — valeur live indisponible"
    st.markdown(head)
    st.plotly_chart(_zone_bar_fig(spec, live), width="stretch", key=f"{key_prefix}_{algo}_{fid}")
    st.caption(f"→ {spec['lever']}")
    if spec.get("divergent_note"):
        st.caption(f"⚠️ {spec['divergent_note']}")


def _live_value(algo: str, fid: str, spec: dict, feats: dict, registry: dict | None = None):
    """Live value only when honestly available (not imputed, not divergent)."""
    if spec.get("live_unavailable") or spec.get("divergent"):
        return None
    return ak.decode_feature_value(algo, fid, feats, registry=registry)


def render_feature_gauges(algo: str, feats: dict) -> None:
    feats = feats or {}
    ids = ak.feature_ids(algo)
    if not ids:
        st.info("Aucune règle de feature disponible pour cet algorithme.")
        return
    zones = ak.ALGO_FEATURE_ZONES[algo]
    st.markdown("#### 🎚️ Curseurs de décision par variable")
    st.caption("Zones : 🔴 malus · ⬜ neutre · 🟢 bonus · trait blanc = valeur de ce titre.")

    available, pedagogic = [], []
    for fid in ids:
        spec = zones[fid]
        live = _live_value(algo, fid, spec, feats)
        (available if live is not None else pedagogic).append((fid, spec, live))

    for fid, spec, live in available:
        _render_one_gauge(algo, fid, spec, live)

    if pedagogic:
        with st.expander(f"Variables sans valeur live ({len(pedagogic)}) — pédagogique"):
            for fid, spec, live in pedagogic:
                _render_one_gauge(algo, fid, spec, None)


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
    st.caption(f"🛡️ {label} : **≥ ~{val:,} streams 7j** (plancher garanti). "
               f"{ak.FORECAST_FLOOR_DISCLAIMER}")


def floor_forecast_text(forecast) -> str | None:
    """Plain-text floor phrasing for tables/tooltips. None if no forecast."""
    if forecast is None:
        return None
    try:
        return f"≥ ~{int(forecast):,} (plancher)"
    except (TypeError, ValueError):
        return None


def render_regressor_badge(algo: str) -> None:
    """'Hungry / conservative model' badge for the volume regressor."""
    note = ak.regressor_note(algo)
    if note:
        st.caption(f"🍽️ Modèle de volume : {note}")


# ── Volume decision gauges (regressor zones) ──────────────────────────────────
def render_volume_gauges(algo: str, feats: dict) -> None:
    """Render the VOLUME (regressor) decision zones — distinct from the entry zones.

    Surfaces the 'quality buys the ticket, volume writes the cheque' insight:
    raw-fuel levers (recent streams, organic traffic) drive volume; saves/playlist
    adds are flagged flat-for-volume. Imputed features (NonAlgoStreams) go to the
    pédagogique expander exactly like the entry gauges.
    """
    feats = feats or {}
    ids = ak.volume_feature_ids(algo)
    if not ids:
        st.info("Pas encore de zones de volume pour cet algorithme.")
        return
    zones = ak.ALGO_VOLUME_ZONES[algo]
    st.markdown("#### 🔊 Curseurs de VOLUME (combien de streams, pas l'entrée)")
    st.caption("La qualité (saves, rétention) achète le **ticket d'entrée** ; le "
               "carburant brut (organique, étincelle récente) écrit le **chèque**.")
    render_regressor_badge(algo)

    available, pedagogic = [], []
    for fid in ids:
        spec = zones[fid]
        live = _live_value(algo, fid, spec, feats, registry=zones)
        (available if live is not None else pedagogic).append((fid, spec, live))

    for fid, spec, live in available:
        _render_one_gauge(algo, fid, spec, live, registry=zones, key_prefix="volgauge")

    if pedagogic:
        with st.expander(f"Variables volume sans valeur live ({len(pedagogic)}) — pédagogique"):
            _imputed = ", ".join(spec["label"] for _fid, spec, _live in pedagogic)
            st.caption(f"⚠️ {_imputed} : features imputées à 0 en production faute de source "
                       "— affichées comme **cibles**, pas valeurs live, jusqu'à la Phase 2 "
                       "(capture live par source/algorithme S4A).")
            for fid, spec, live in pedagogic:
                _render_one_gauge(algo, fid, spec, None, registry=zones, key_prefix="volgauge")


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
    lines = [f"**🧾 Autopsie {algo_label}** — point de départ moyen : "
             f"~{baseline:,.0f} → prédiction : **~{prediction:,.0f}**."]
    if neg:
        worst = ", ".join(f"{c['label']} ({c['value']:,.0f})" for c in neg)
        lines.append(f"❌ Ce qui tire vers le bas : {worst}.")
    if pos:
        best = ", ".join(f"{c['label']} (+{c['value']:,.0f})" for c in pos)
        lines.append(f"✅ Ce qui soutient : {best}.")
    st.markdown("  \n".join(lines))


# ── Prescriptive coach (ranked to-do list) ────────────────────────────────────
def render_coach(algo: str, feats: dict) -> None:
    """Ranked prescriptive actions for an algo. Velocity-too-high → smooth advice
    (concrete spend cut shown in the Budget tab); others → raise-to-target."""
    feats = feats or {}
    if not ak.feature_ids(algo):
        return
    st.markdown("##### 🧭 Coach prescriptif")
    actions = ak.build_coach_actions(algo, feats)
    if not actions:
        st.success("✅ Aucune action critique : les leviers mesurables sont en zone neutre/bonus.")
    for i, a in enumerate(actions, 1):
        if a["kind"] == "smooth":
            st.error(
                f"**{i}. Lisser la vélocité** — actuelle {a['current']:.2f}. {a['lever']} "
                "→ réduis le budget pub (~−30%) ; montant concret dans l'onglet Budget & ROI."
            )
        else:
            st.warning(
                f"**{i}. {a['label']}** — {a['current']:,.0f} {a['unit']} "
                f"(objectif {a['target']:,.0f}, manque {a['gap']:,.0f}). {a['lever']}"
            )
    if algo == "RADIO":
        st.info(
            "🎫 Vérifie **Discovery Mode** (Spotify for Artists) : fort levier Radio "
            "(pay-to-play, −30% royalties) — non mesuré automatiquement."
        )
